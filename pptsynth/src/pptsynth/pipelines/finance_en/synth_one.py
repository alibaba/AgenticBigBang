"""Synthesize one PPTSynth economics/finance task case from one PDF.

Sequential pipeline: Stage 1-3 → Stage 4 (Audit) → conditional Stage 4b
(Verify-Refine) → optional Stage 4c (Re-Audit) → Stage 5 (Pack).
Per-stage retry; stage-level skip on incomplete/successful prior runs.
The family profile (A corporate / B macro) is injected into every LLM stage.
Output: out_root/finance_en/<slug>/
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .stages import (
    run_audit,
    run_pack,
    run_profile,
    run_rubric,
    run_task,
    run_verify_refine,
    should_trigger_verify_refine,
)
from .stages._runner import StageOutcome
from .family_registry import FamilyProfile


_STAGE_ARTIFACTS: dict[str, list[str]] = {
    "1_profile": ["_paper_card.json"],
    "2_task": ["generation_task/instructions.md"],
    "3_rubric": ["generation_task/judge_prompt.json"],
    "4_audit": ["_audit_report.json"],
    "5_pack": ["generation_task/statistics.yaml", "case_status.json"],
}


@dataclass
class CaseResult:
    case_slug: str
    case_dir: Path
    success: bool
    duration_s: float
    family: str = ""
    audit_pass: bool | None = None
    verify_refined: bool | None = None
    stage_outcomes: list[StageOutcome] = field(default_factory=list)
    error: str | None = None


def _stage_done(case_dir: Path, stage: str) -> bool:
    return all((case_dir / rel).exists() for rel in _STAGE_ARTIFACTS[stage])


async def _run_stage_with_retry(
    *,
    name: str,
    fn,
    case_slug: str,
    case_dir: Path,
    retries: int,
    **kwargs,
) -> StageOutcome:
    last: StageOutcome | None = None
    retry_hint: str | None = None
    resume_sid: str | None = None
    for attempt in range(1, retries + 2):
        out = await fn(case_slug=case_slug, case_dir=case_dir, retry_hint=retry_hint,
                       resume_session_id=resume_sid, **kwargs)
        last = out
        if out.ok:
            return out
        retry_note = case_dir / "_stage_logs" / f"{name}.retry_{attempt}.txt"
        retry_note.parent.mkdir(parents=True, exist_ok=True)
        retry_note.write_text(
            f"attempt {attempt} failed"
            + (f" (will resume session {out.session_id})" if out.session_id and out.parsed_payload else "")
            + f": {out.error}\n",
            encoding="utf-8",
        )
        retry_hint = (out.error or "")[:1400]
        # Resume policy: only when the failed attempt exited cleanly (payload
        # parsed, session persisted) — i.e. validation-type failures. Crash /
        # timeout failures get a fresh session (no usable transcript).
        resume_sid = out.session_id if (out.session_id and out.parsed_payload) else None
    assert last is not None
    return last


async def synth_one(
    *,
    pdf_path: Path,
    case_slug: str,
    out_root: Path,
    family_profile: FamilyProfile | None = None,
    doc_meta: dict | None = None,
    model: str | None = None,
    max_budget_usd: float | None = None,
    skip_done: bool = True,
    retries_per_stage: int = 1,
    max_thinking_tokens: int | None = None,
    effort: str | None = None,
) -> CaseResult:
    """Run all stages for one finance document. Case dir: out_root/finance_en/<slug>/"""
    case_dir = out_root / "finance_en" / case_slug
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "_stage_logs").mkdir(exist_ok=True)
    (case_dir / "generation_task").mkdir(exist_ok=True)

    material = case_dir / "material.pdf"
    if not material.exists():
        shutil.copy2(pdf_path, material)

    # Ground-truth metadata for Stage 1 + Stage 5.
    if doc_meta is not None:
        meta_path = case_dir / "_case_meta.json"
        if not meta_path.exists():
            meta_path.write_text(
                json.dumps(doc_meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    family = family_profile.family if family_profile else (doc_meta or {}).get("family", "")

    start = time.monotonic()
    outcomes: list[StageOutcome] = []

    _kw = dict(
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
        effort=effort,
        family_profile=family_profile,
    )

    # Stage 1
    if skip_done and _stage_done(case_dir, "1_profile"):
        outcomes.append(StageOutcome(
            stage="1_profile", case_slug=case_slug, ok=True, duration_s=0.0,
            error="skipped (artifacts present)",
        ))
    else:
        out = await _run_stage_with_retry(
            name="1_profile", fn=run_profile, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(
                case_slug=case_slug, case_dir=case_dir, success=False, family=family,
                duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                error=f"stage 1_profile failed: {out.error}",
            )

    # Stage 2
    if skip_done and _stage_done(case_dir, "2_task"):
        outcomes.append(StageOutcome(
            stage="2_task", case_slug=case_slug, ok=True, duration_s=0.0,
            error="skipped (artifacts present)",
        ))
    else:
        out = await _run_stage_with_retry(
            name="2_task", fn=run_task, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(
                case_slug=case_slug, case_dir=case_dir, success=False, family=family,
                duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                error=f"stage 2_task failed: {out.error}",
            )

    # Stage 3
    stage3_skipped = False
    if skip_done and _stage_done(case_dir, "3_rubric"):
        stage3_skipped = True
        outcomes.append(StageOutcome(
            stage="3_rubric", case_slug=case_slug, ok=True, duration_s=0.0,
            error="skipped (artifacts present)",
        ))
    else:
        out = await _run_stage_with_retry(
            name="3_rubric", fn=run_rubric, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(
                case_slug=case_slug, case_dir=case_dir, success=False, family=family,
                duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                error=f"stage 3_rubric failed: {out.error}",
            )

    # Stage 4 — audit. On a fresh Stage 3 it must run. On resume of a fully-done
    # case (Stage 3 skipped AND audit report on disk), skip it.
    audit_pass: bool | None = None
    audit_scores: dict[str, int] = {}
    if skip_done and stage3_skipped and _stage_done(case_dir, "4_audit"):
        try:
            _rep = json.loads((case_dir / "_audit_report.json").read_text(encoding="utf-8"))
            audit_pass = bool(_rep.get("pass"))
        except Exception:
            audit_pass = None
        out = StageOutcome(
            stage="4_audit", case_slug=case_slug, ok=True, duration_s=0.0,
            error="skipped (already audited)",
        )
        outcomes.append(out)
    else:
        out = await _run_stage_with_retry(
            name="4_audit", fn=run_audit, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if out.ok and out.parsed_payload:
            audit_pass = bool(out.parsed_payload.get("audit_pass"))
            audit_scores = out.parsed_payload.get("audit_scores") or {}

    # Stage 4b — conditional verify-refine (family_profile not needed here).
    verify_refined = False
    if out.ok and audit_scores:
        trigger, low_axes = should_trigger_verify_refine(audit_scores)
        if trigger:
            if skip_done and (case_dir / "_verify_refine_report.json").exists():
                outcomes.append(StageOutcome(
                    stage="4b_verify_refine", case_slug=case_slug, ok=True,
                    duration_s=0.0,
                    error="skipped (already verified)",
                ))
                verify_refined = True
            else:
                vr_out = await _run_stage_with_retry(
                    name="4b_verify_refine", fn=run_verify_refine,
                    case_slug=case_slug, case_dir=case_dir,
                    retries=retries_per_stage, model=model,
                    max_budget_usd=max_budget_usd,
                    max_thinking_tokens=max_thinking_tokens,
                    effort=effort,
                    low_axes=low_axes,
                )
                outcomes.append(vr_out)
                if vr_out.ok:
                    verify_refined = True
                    orig_audit = case_dir / "_audit_report.json"
                    backup = case_dir / "_audit_report_pre_verify.json"
                    if orig_audit.exists() and not backup.exists():
                        shutil.copy2(orig_audit, backup)
                        orig_audit.unlink()
                    reaudit_out = await _run_stage_with_retry(
                        name="reaudit", fn=run_audit,
                        case_slug=case_slug, case_dir=case_dir,
                        retries=0, **_kw,
                    )
                    outcomes.append(reaudit_out)
                    if reaudit_out.ok and reaudit_out.parsed_payload:
                        audit_pass = bool(reaudit_out.parsed_payload.get("audit_pass"))
                        reaudit_scores = reaudit_out.parsed_payload.get("audit_scores") or {}
                        needs_review = any(
                            isinstance(v, int) and v <= 2
                            for v in reaudit_scores.values()
                        )
                        if needs_review:
                            (case_dir / "_needs_human_review.txt").write_text(
                                f"Post-verify-refine re-audit still has axes ≤2: {reaudit_scores}\n",
                                encoding="utf-8",
                            )

    # Stage 5 — pack (deterministic; always run last).
    pack_out = await run_pack(case_slug=case_slug, case_dir=case_dir)
    outcomes.append(pack_out)

    success = all(
        o.ok for o in outcomes if o.stage != "4b_verify_refine"
    )
    return CaseResult(
        case_slug=case_slug,
        case_dir=case_dir,
        success=success,
        duration_s=time.monotonic() - start,
        family=family,
        audit_pass=audit_pass,
        verify_refined=verify_refined,
        stage_outcomes=outcomes,
        error=None if success else "; ".join(
            f"{o.stage}: {o.error}" for o in outcomes
            if not o.ok and o.error and o.stage != "4b_verify_refine"
        ),
    )


def serialize_case_result(r: CaseResult) -> dict:
    """For per-batch manifest emission."""
    return {
        "case_slug": r.case_slug,
        "case_dir": str(r.case_dir),
        "family": r.family,
        "success": r.success,
        "duration_s": round(r.duration_s, 2),
        "audit_pass": r.audit_pass,
        "verify_refined": r.verify_refined,
        "error": r.error,
        "stages": [
            {
                "stage": o.stage,
                "ok": o.ok,
                "duration_s": round(o.duration_s, 2),
                "session_id": o.session_id,
                "cost_usd": o.cost_usd,
                "error": o.error,
            }
            for o in r.stage_outcomes
        ],
    }
