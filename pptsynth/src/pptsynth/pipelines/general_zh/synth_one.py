"""Synthesize one broad-domain task case from one document PDF.

Sequential pipeline: Stage 1-3 → Stage 4 (Audit) → conditional Stage 4b
(Verify-Refine + Re-Audit) → Stage 5 (Pack).
Domain pack injected throughout for domain-specific prompt composition.
Output: out_root/<primary>/<secondary>/<slug>/
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
from .domain_registry import DomainPack


_STAGE_ARTIFACTS: dict[str, list[str]] = {
    "1_profile": ["_doc_card.json"],
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
    primary: str = ""
    secondary: str = ""
    audit_pass: bool | None = None
    verify_refined: bool | None = None
    stage_outcomes: list[StageOutcome] = field(default_factory=list)
    error: str | None = None


def _stage_done(case_dir: Path, stage: str) -> bool:
    return all((case_dir / rel).exists() for rel in _STAGE_ARTIFACTS[stage])


def _case_fully_done(case_dir: Path) -> bool:
    status_path = case_dir / "case_status.json"
    if not status_path.exists():
        return False
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("audit", {}).get("passed") is True


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
    for attempt in range(1, retries + 2):
        out = await fn(case_slug=case_slug, case_dir=case_dir, **kwargs)
        last = out
        if out.ok:
            return out
        retry_note = case_dir / "_stage_logs" / f"{name}.retry_{attempt}.txt"
        retry_note.parent.mkdir(parents=True, exist_ok=True)
        retry_note.write_text(f"attempt {attempt} failed: {out.error}\n", encoding="utf-8")
    assert last is not None
    return last


async def synth_one(
    *,
    pdf_path: Path,
    case_slug: str,
    out_root: Path,
    primary: str = "",
    secondary: str = "",
    domain_pack: DomainPack | None = None,
    model: str | None = None,
    max_budget_usd: float | None = None,
    skip_done: bool = True,
    retries_per_stage: int = 1,
    max_thinking_tokens: int | None = None,
) -> CaseResult:
    """Run all stages for one document. Case dir: out_root/<primary>/<secondary>/<slug>/"""
    # Build case dir with primary/secondary path components
    if primary and secondary:
        case_dir = out_root / "general_zh" / primary / secondary / case_slug
    elif primary:
        case_dir = out_root / "general_zh" / primary / case_slug
    else:
        case_dir = out_root / "general_zh" / case_slug

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "_stage_logs").mkdir(exist_ok=True)
    (case_dir / "generation_task").mkdir(exist_ok=True)

    material = case_dir / "material.pdf"
    if not material.exists():
        shutil.copy2(pdf_path, material)

    if skip_done and _case_fully_done(case_dir):
        return CaseResult(
            case_slug=case_slug,
            case_dir=case_dir,
            success=True,
            duration_s=0.0,
            primary=primary,
            secondary=secondary,
            audit_pass=True,
        )

    start = time.monotonic()
    outcomes: list[StageOutcome] = []

    _kw = dict(
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
        domain_pack=domain_pack,
    )

    # Stage 1
    if skip_done and _stage_done(case_dir, "1_profile"):
        outcomes.append(StageOutcome(stage="1_profile", case_slug=case_slug, ok=True, duration_s=0.0,
                                     error="skipped (artifacts present)"))
    else:
        out = await _run_stage_with_retry(
            name="1_profile", fn=run_profile, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(case_slug=case_slug, case_dir=case_dir, success=False,
                              duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                              primary=primary, secondary=secondary,
                              error=f"stage 1_profile failed: {out.error}")

    # Stage 2
    if skip_done and _stage_done(case_dir, "2_task"):
        outcomes.append(StageOutcome(stage="2_task", case_slug=case_slug, ok=True, duration_s=0.0,
                                     error="skipped (artifacts present)"))
    else:
        out = await _run_stage_with_retry(
            name="2_task", fn=run_task, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(case_slug=case_slug, case_dir=case_dir, success=False,
                              duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                              primary=primary, secondary=secondary,
                              error=f"stage 2_task failed: {out.error}")

    # Stage 3
    if skip_done and _stage_done(case_dir, "3_rubric"):
        outcomes.append(StageOutcome(stage="3_rubric", case_slug=case_slug, ok=True, duration_s=0.0,
                                     error="skipped (artifacts present)"))
    else:
        out = await _run_stage_with_retry(
            name="3_rubric", fn=run_rubric, case_slug=case_slug, case_dir=case_dir,
            retries=retries_per_stage, **_kw,
        )
        outcomes.append(out)
        if not out.ok:
            return CaseResult(case_slug=case_slug, case_dir=case_dir, success=False,
                              duration_s=time.monotonic() - start, stage_outcomes=outcomes,
                              primary=primary, secondary=secondary,
                              error=f"stage 3_rubric failed: {out.error}")

    # Stage 4 — always run
    out = await _run_stage_with_retry(
        name="4_audit", fn=run_audit, case_slug=case_slug, case_dir=case_dir,
        retries=retries_per_stage, **_kw,
    )
    outcomes.append(out)
    audit_pass: bool | None = None
    audit_scores: dict[str, int] = {}
    if out.ok and out.parsed_payload:
        audit_pass = bool(out.parsed_payload.get("audit_pass"))
        audit_scores = out.parsed_payload.get("audit_scores") or {}

    # Stage 4b — conditional verify-refine (domain_pack not needed here)
    verify_refined = False
    if out.ok and audit_scores:
        trigger, low_axes = should_trigger_verify_refine(audit_scores)
        if trigger:
            if skip_done and (case_dir / "_verify_refine_report.json").exists():
                outcomes.append(StageOutcome(stage="4b_verify_refine", case_slug=case_slug,
                                             ok=True, duration_s=0.0,
                                             error="skipped (already verified)"))
                verify_refined = True
            else:
                vr_out = await _run_stage_with_retry(
                    name="4b_verify_refine", fn=run_verify_refine,
                    case_slug=case_slug, case_dir=case_dir,
                    retries=retries_per_stage,
                    model=model, max_budget_usd=max_budget_usd,
                    max_thinking_tokens=max_thinking_tokens,
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

    # Stage 5
    pack_out = await run_pack(case_slug=case_slug, case_dir=case_dir, domain_pack=domain_pack)
    outcomes.append(pack_out)

    success = all(o.ok for o in outcomes if o.stage != "4b_verify_refine")
    return CaseResult(
        case_slug=case_slug,
        case_dir=case_dir,
        success=success,
        duration_s=time.monotonic() - start,
        primary=primary,
        secondary=secondary,
        audit_pass=audit_pass,
        verify_refined=verify_refined,
        stage_outcomes=outcomes,
        error=None if success else "; ".join(
            f"{o.stage}: {o.error}" for o in outcomes
            if not o.ok and o.error and o.stage != "4b_verify_refine"
        ),
    )


def serialize_case_result(r: CaseResult) -> dict:
    return {
        "case_slug": r.case_slug,
        "case_dir": str(r.case_dir),
        "primary": r.primary,
        "secondary": r.secondary,
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
