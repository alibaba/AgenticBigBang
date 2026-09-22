"""Stage 4b: Conditional Verify-Refine (AB2 — with regression protection).

Runs only when Stage 4 Audit scores trigger it (low scores on anchor
specificity, trap coverage, atomicity, or key_numbers coverage). Performs
per-item discriminability assessment, trap coverage cross-check, targeted
revision, deduplication, and spot checking — all in a single LLM call.

AB2 additions vs AB:
- Widened post-VR count bounds to [9,35]/[8,35] to match post-Audit ranges
- Regression detection: reverts if C1 or C2 count drops >20% vs pre-VR
- Coverage preservation: reverts if substantive items are lost
- Pre-VR counts injected into trigger context and user prompt

Backs up the original judge_prompt.json before modification; restores it
if the stage fails or regression is detected (graceful degradation).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import jsonschema  # type: ignore

from ._runner import StageOutcome, run_stage, extract_final_json

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

_CRITICAL_AXES = frozenset({
    "checklist_anchor_specificity",
    "trap_coverage",
    "atomicity_check",
    "key_numbers_coverage",
})

_FIGURE_REF_RE = re.compile(
    r"\bFigure\s+\d+|\bTable\s+\d+|\bFig\.\s*\d+", re.IGNORECASE
)


def should_trigger(audit_scores: dict[str, int]) -> tuple[bool, list[str]]:
    """Decide whether verify-refine should run based on audit scores.

    Returns (trigger: bool, low_axes: list[str]).
    """
    if not audit_scores:
        return False, []
    low_axes = [
        ax for ax, score in audit_scores.items()
        if isinstance(score, int) and score <= 3
    ]
    trigger = bool(_CRITICAL_AXES & set(low_axes)) or len(low_axes) >= 3
    return trigger, low_axes

_USER_PROMPT_TEMPLATE = """\
Stage 4b: Verify-Refine (conditional).

This case was triggered for verify-refine because the following audit axes
scored ≤3: {low_axes_str}

The current rubric has {pre_c1} C1 items and {pre_c2} C2 items.

REGRESSION CONSTRAINT: Your revision must NOT reduce C1 below {min_c1} or
C2 below {min_c2}. Do NOT merge items scored 3-5. Only items scored 1-2
may be removed, rewritten, or split. If in doubt, preserve the item.

Inputs in this working directory:
- ./generation_task/judge_prompt.json (the rubric to assess and revise)
- ./_paper_card.json (ground truth)
- ./_field_manifest.txt (mandatory coverage manifest)
- ./_audit_report.json (the audit that triggered this step)
- ./_verify_refine_trigger.json (trigger context: which axes failed and why)
- ./_verify_refine_report.schema.json (schema for your output report)

Follow the 5 tasks in your system prompt (discriminability scoring, traps
cross-check, inline revision, dedup, spot check). Edit judge_prompt.json
in place. Then write ./_verify_refine_report.json and emit the same JSON
as your final message (no prose, no markdown fences).
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    """Copy the verify-refine report schema into the case dir and ensure
    the field manifest exists."""
    schema_src = SCHEMAS_DIR / "verify_refine_report.schema.json"
    schema_dst = case_dir / "_verify_refine_report.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())

    # Ensure field manifest exists (normally created by stage 3, but
    # regenerate if missing — e.g. when resuming from a prior run).
    manifest_path = case_dir / "_field_manifest.txt"
    pc_path = case_dir / "_paper_card.json"
    if not manifest_path.exists() and pc_path.exists():
        try:
            from ..extract_field_manifest import build_manifest

            pc = json.loads(pc_path.read_text(encoding="utf-8"))
            manifest_path.write_text(build_manifest(pc), encoding="utf-8")
        except Exception:
            pass


def _write_trigger_context(case_dir: Path, low_axes: list[str]) -> None:
    """Write trigger context so the LLM knows why it was invoked and what to focus on."""
    audit_path = case_dir / "_audit_report.json"
    audit_scores: dict = {}
    if audit_path.exists():
        try:
            audit_data = json.loads(audit_path.read_text(encoding="utf-8"))
            audit_scores = audit_data.get("scores") or {}
        except (json.JSONDecodeError, KeyError):
            pass

    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    pre_c1, pre_c2 = _get_rubric_counts(judge_path)

    low_scores = {ax: audit_scores.get(ax, "?") for ax in low_axes}
    ctx = {
        "trigger_reasons": [f"{ax} scored {low_scores[ax]}" for ax in low_axes],
        "audit_scores": audit_scores,
        "low_axes": low_scores,
        "pre_verify_counts": {"C1": pre_c1, "C2": pre_c2},
        "regression_constraints": {
            "max_c1_drop_pct": int(_MAX_COUNT_DROP_RATIO * 100),
            "max_c2_drop_pct": int(_MAX_COUNT_DROP_RATIO * 100),
            "min_c1_after": max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO))),
            "min_c2_after": max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO))),
        },
        "guidance": (
            "Focus your revision on the axes listed in low_axes. "
            "Items contributing to low scores on these axes are the "
            "highest-priority targets for improvement. "
            "CRITICAL: Your revision must NOT reduce C1 count below "
            f"{max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO)))} "
            f"(current: {pre_c1}) or C2 count below "
            f"{max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO)))} "
            f"(current: {pre_c2}). "
            "Do NOT merge items scored 3-5. Only remove/rewrite items scored 1-2."
        ),
    }
    (case_dir / "_verify_refine_trigger.json").write_text(
        json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _backup_rubric(case_dir: Path) -> Path:
    """Back up judge_prompt.json before VR modifies it. Returns backup path."""
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    if judge_path.exists() and not backup_path.exists():
        shutil.copy2(judge_path, backup_path)
    return backup_path


def _restore_rubric_on_failure(case_dir: Path) -> None:
    """Restore the original rubric if VR produced invalid output."""
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    if backup_path.exists():
        shutil.copy2(backup_path, judge_path)


def _heal_judge_json(case_dir: Path) -> list[str]:
    """Re-serialize judge_prompt.json to fix formatting damage from LLM Edit."""
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    if not judge_path.exists():
        return ["judge_prompt.json missing after stage"]
    raw = judge_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            repaired = raw.replace('",\\n', '",\n').replace('\\n    "', '\n    "')
            data = json.loads(repaired)
        except json.JSONDecodeError as e:
            return [f"judge_prompt.json unfixable JSON: {e}"]
    judge_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return []


def _validate_report(report: dict) -> list[str]:
    """Validate the verify-refine report against its JSON Schema."""
    schema = json.loads(
        (SCHEMAS_DIR / "verify_refine_report.schema.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda e: list(e.path))
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors
    ]


_MAX_COUNT_DROP_RATIO = 0.20


def _get_rubric_counts(path: Path) -> tuple[int, int]:
    """Return (c1_count, c2_count) from a judge_prompt.json file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        c1 = data.get("material_dependent_checklist_1") or []
        c2 = data.get("material_dependent_checklist_2") or []
        return len(c1), len(c2)
    except (json.JSONDecodeError, OSError):
        return 0, 0


def _get_rubric_items(path: Path) -> tuple[list[str], list[str]]:
    """Return (c1_items, c2_items) from a judge_prompt.json file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        c1 = data.get("material_dependent_checklist_1") or []
        c2 = data.get("material_dependent_checklist_2") or []
        return c1, c2
    except (json.JSONDecodeError, OSError):
        return [], []


def _extract_item_key(item: str) -> str:
    """Extract the bold question text as a rough fingerprint for coverage comparison."""
    match = re.search(r'\*\*(.+?)\?\*\*', item, re.DOTALL)
    return match.group(1).strip().lower() if match else item.strip().lower()[:80]


def _check_regression(case_dir: Path) -> list[str]:
    """Compare post-VR rubric against pre-VR backup. Returns issues if regression detected."""
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    if not backup_path.exists() or not judge_path.exists():
        return []

    pre_c1, pre_c2 = _get_rubric_counts(backup_path)
    post_c1, post_c2 = _get_rubric_counts(judge_path)
    issues: list[str] = []

    if pre_c1 > 0 and (pre_c1 - post_c1) / pre_c1 > _MAX_COUNT_DROP_RATIO:
        issues.append(
            f"C1 count regression: {pre_c1} -> {post_c1} "
            f"(dropped {(pre_c1 - post_c1) / pre_c1:.0%}, max allowed {_MAX_COUNT_DROP_RATIO:.0%})"
        )

    if pre_c2 > 0 and (pre_c2 - post_c2) / pre_c2 > _MAX_COUNT_DROP_RATIO:
        issues.append(
            f"C2 count regression: {pre_c2} -> {post_c2} "
            f"(dropped {(pre_c2 - post_c2) / pre_c2:.0%}, max allowed {_MAX_COUNT_DROP_RATIO:.0%})"
        )

    pre_c1_items, pre_c2_items = _get_rubric_items(backup_path)
    post_c1_items, post_c2_items = _get_rubric_items(judge_path)

    pre_keys = {_extract_item_key(item) for item in pre_c1_items + pre_c2_items}
    post_keys = {_extract_item_key(item) for item in post_c1_items + post_c2_items}

    lost_keys = pre_keys - post_keys
    if len(lost_keys) > len(pre_keys) * _MAX_COUNT_DROP_RATIO:
        issues.append(
            f"coverage regression: {len(lost_keys)} items lost out of {len(pre_keys)} "
            f"(>{_MAX_COUNT_DROP_RATIO:.0%} threshold)"
        )

    return issues


def _static_checks_judge(case_dir: Path) -> list[str]:
    """Run static checks on the (possibly revised) judge_prompt.json.

    Mirrors the checks in stage3_rubric._static_checks.
    """
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    issues: list[str] = []
    if not judge_path.exists():
        return ["judge_prompt.json not on disk after verify-refine"]
    try:
        data = json.loads(judge_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"judge_prompt.json invalid JSON: {e}"]
    if not isinstance(data, dict):
        return ["judge_prompt.json root is not an object"]

    c1 = data.get("material_dependent_checklist_1") or []
    c2 = data.get("material_dependent_checklist_2") or []
    if not isinstance(c1, list) or not isinstance(c2, list):
        issues.append("checklist values must be arrays")
        return issues
    if not (9 <= len(c1) <= 35):
        issues.append(f"completeness count out of [9,35]: {len(c1)}")
    if not (8 <= len(c2) <= 35):
        issues.append(f"correctness count out of [8,35]: {len(c2)}")

    all_items = c1 + c2
    fig_ref_count = sum(1 for item in all_items if _FIGURE_REF_RE.search(item))
    if fig_ref_count > len(all_items) * 0.15:
        issues.append(
            f"{fig_ref_count}/{len(all_items)} items reference Figure/Table "
            f"numbers — describe CONTENT instead"
        )
    return issues


_RESUME_PROMPT_TEMPLATE = """\
Your previous attempt in this session FAILED harness validation:

{error}

Fix the existing artifact IN PLACE with minimal targeted edits (do not
regenerate it from scratch, do not re-read material.pdf unless strictly
necessary). The error list above may be TRUNCATED — after fixing the listed
violations, re-check the ENTIRE artifact against the mounted schema (every
object at every level: exact required field names, no additional properties)
and fix all remaining violations of the same kind. Then finish exactly as
originally instructed, emitting the same final JSON message format.
"""

async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 30,
    timeout_s: int = 1500,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
    effort: str | None = None,
    retry_hint: str | None = None,
    resume_session_id: str | None = None,
    low_axes: list[str] | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)

    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    pre_c1, pre_c2 = _get_rubric_counts(judge_path)

    _backup_rubric(case_dir)
    _write_trigger_context(case_dir, low_axes or [])

    low_axes_str = ", ".join(low_axes) if low_axes else "(none specified)"
    min_c1 = max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO)))
    min_c2 = max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO)))
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        low_axes_str=low_axes_str,
        pre_c1=pre_c1,
        pre_c2=pre_c2,
        min_c1=min_c1,
        min_c2=min_c2,
    )

    system_prompt_file = PROMPTS_DIR / "verify_refine_system.md"
    out = await run_stage(
        stage_name="4b_verify_refine",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=user_prompt,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Edit", "Write", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
        effort=effort,
        resume_session_id=resume_session_id,
    )
    if not out.ok:
        _restore_rubric_on_failure(case_dir)
        return out

    # --- Heal JSON formatting damage from LLM Edit ---
    heal_issues = _heal_judge_json(case_dir)
    if heal_issues:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = "post-edit JSON heal failed: " + "; ".join(heal_issues)
        return out

    # --- Read or extract the verify-refine report ---
    report_path = case_dir / "_verify_refine_report.json"
    report: dict | None = None
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            _restore_rubric_on_failure(case_dir)
            out.ok = False
            out.error = f"_verify_refine_report.json present but unparseable: {e}"
            return out
    if report is None:
        report = extract_final_json(out.raw_result)
        if report is None:
            _restore_rubric_on_failure(case_dir)
            out.ok = False
            out.error = "verify-refine produced no parseable report"
            return out
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # --- Validate report against schema ---
    schema_errors = _validate_report(report)
    if schema_errors:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = (
            "verify_refine_report schema violations: "
            + "; ".join(schema_errors[:5])
        )
        return out

    # --- Static checks on the revised judge_prompt.json ---
    judge_issues = _static_checks_judge(case_dir)
    if judge_issues:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = (
            "post-verify-refine judge_prompt checks: "
            + "; ".join(judge_issues[:6])
        )
        return out

    # --- Regression protection: revert if VR caused count/coverage regression ---
    regression_issues = _check_regression(case_dir)
    if regression_issues:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = (
            "verify-refine regression detected (reverted to pre-VR rubric): "
            + "; ".join(regression_issues)
        )
        return out

    out.parsed_payload = (out.parsed_payload or {}) | {
        "verified": report.get("verified"),
        "revision_round": report.get("revision_round"),
        "trigger_axes": report.get("trigger_axes"),
        "revisions_count": len(report.get("revisions") or []),
        "dedup_count": len(report.get("dedup_actions") or []),
        "traps_covered_after": (report.get("traps_coverage") or {}).get(
            "covered_after"
        ),
    }
    return out
