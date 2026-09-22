"""Stage 3: Author judge_prompt.json — completeness + correctness checklists.

Changes vs original pptsynth_synth:
- Generates _field_manifest.txt from paper_card before calling the LLM
- User prompt references the manifest
- Wider accepted item count ranges (C1: 9-35, C2: 8-35)
- Tighter per-item character limit (600 -> 550)
- Figure-number reference detection
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ._runner import StageOutcome, run_stage
from ..family_registry import FamilyProfile
from ..prompt_compose import compose

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PKG_DIR = Path(__file__).resolve().parent.parent

_USER_PROMPT = """\
Stage 3: Author the Judge Rubric.

Inputs in this working directory:
- ./_paper_card.json
- ./_field_manifest.txt  (auto-generated — lists ALL fields you must cover)
- ./generation_task/instructions.md

Read _field_manifest.txt FIRST. It lists every key_number, trap, and
confusable key_term you MUST cover. Use the suggested item count as a guide.

Write a single file ./generation_task/judge_prompt.json with exactly two
keys: material_dependent_checklist_1 (completeness items) and
material_dependent_checklist_2 (correctness items).

Item count is driven by the paper's content (see manifest for suggested
count). Do NOT force a fixed number — let the paper's key_numbers, traps,
and key_terms determine how many items you need.

Match the PPTSynth academic checklist style: each item is
one Markdown-flavored string that begins and ends with a newline, posed
as a binary question, with concrete paper-specific anchors.

After writing, emit one JSON object as your final assistant message:
{"stage":"rubric","ok":true,"completeness_count":<int>,"correctness_count":<int>,"anchors_extracted_from_paper_card":<int>,"key_numbers_covered":<int>,"traps_covered":<int>,"confusable_terms_covered":<int>,"warnings":[]}

Never use Glob/Grep/Read/Bash on paths outside the current working directory
(e.g. `..` or absolute parent paths) — parent directories are not readable.
"""

_FIGURE_REF_RE = re.compile(
    r"\bFigure\s+\d+|\bTable\s+[A-Z]?\.?\d+|\bFig\.\s*\d+|\bChart\s+\d+|\bExhibit\s+\d+|\bBox\s+\d+",
    re.IGNORECASE,
)


def _generate_field_manifest(case_dir: Path) -> None:
    """Generate _field_manifest.txt from _paper_card.json."""
    from ..extract_field_manifest import build_manifest

    pc_path = case_dir / "_paper_card.json"
    if not pc_path.exists():
        return
    pc = json.loads(pc_path.read_text(encoding="utf-8"))
    manifest = build_manifest(pc)
    (case_dir / "_field_manifest.txt").write_text(manifest, encoding="utf-8")


def _static_checks(judge_path: Path, case_dir: Path) -> list[str]:
    issues: list[str] = []
    if not judge_path.exists():
        return ["judge_prompt.json not on disk"]
    try:
        data = json.loads(judge_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"judge_prompt.json invalid JSON: {e}"]
    if not isinstance(data, dict):
        return ["judge_prompt.json root is not an object"]
    keys = set(data.keys())
    expected = {"material_dependent_checklist_1", "material_dependent_checklist_2"}
    if keys != expected:
        issues.append(f"keys must be exactly {expected}; got {sorted(keys)}")
    c1 = data.get("material_dependent_checklist_1") or []
    c2 = data.get("material_dependent_checklist_2") or []
    if not isinstance(c1, list) or not isinstance(c2, list):
        issues.append("checklist values must be arrays")
        return issues
    if not (9 <= len(c1) <= 35):
        issues.append(f"completeness count out of [9,35]: {len(c1)}")
    if not (8 <= len(c2) <= 35):
        issues.append(f"correctness count out of [8,35]: {len(c2)}")
    for i, item in enumerate(c1, 1):
        if not isinstance(item, str):
            issues.append(f"completeness[{i}] not a string")
            continue
        if "?" not in item:
            issues.append(f"completeness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"completeness[{i}] missing bold question marker")
        if len(item) > 550:
            issues.append(f"completeness[{i}] too long ({len(item)} chars)")
    for i, item in enumerate(c2, 1):
        if not isinstance(item, str):
            issues.append(f"correctness[{i}] not a string")
            continue
        if "?" not in item:
            issues.append(f"correctness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"correctness[{i}] missing bold question marker")
        if "If **no**" not in item:
            issues.append(f"correctness[{i}] missing 'If **no**' instruction")
        if len(item) > 550:
            issues.append(f"correctness[{i}] too long ({len(item)} chars)")

    # Check figure/table number references
    all_items = c1 + c2
    fig_ref_count = sum(1 for item in all_items if _FIGURE_REF_RE.search(item))
    if fig_ref_count > len(all_items) * 0.15:
        issues.append(
            f"{fig_ref_count}/{len(all_items)} items reference Figure/Table "
            f"numbers — describe CONTENT instead"
        )

    # Check key_numbers coverage
    pc_path = case_dir / "_paper_card.json"
    if pc_path.exists():
        try:
            pc = json.loads(pc_path.read_text(encoding="utf-8"))
            key_numbers = pc.get("key_numbers") or []
            traps = pc.get("traps") or []
            c2_text = " ".join(c2).lower()

            # Rough coverage check for traps
            trap_kinds_covered = set()
            for trap in traps:
                cf = trap["correct_form"][:40].lower()
                if cf in c2_text or any(w in c2_text for w in cf.split()[:3]):
                    trap_kinds_covered.add(trap["kind"])
            if len(trap_kinds_covered) < min(3, len(traps)):
                issues.append(
                    f"trap coverage low: only {len(trap_kinds_covered)} trap "
                    f"kinds referenced out of {len(set(t['kind'] for t in traps))}"
                )
        except (json.JSONDecodeError, KeyError):
            pass

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
    family_profile: FamilyProfile | None = None,
) -> StageOutcome:
    # Generate field manifest before calling the LLM
    _generate_field_manifest(case_dir)

    base_system = PROMPTS_DIR / "3_rubric_system.md"
    system_prompt_file = compose("3_rubric", base_system, case_dir, family_profile)
    if resume_session_id:
        user_prompt = _RESUME_PROMPT_TEMPLATE.format(error=retry_hint or "unknown error")
    else:
        user_prompt = _USER_PROMPT
        if retry_hint:
            user_prompt += (
                "\n\nPREVIOUS ATTEMPT FAILED with this harness error — do not repeat it:\n"
                + retry_hint + "\n"
            )
    out = await run_stage(
        stage_name="3_rubric",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=user_prompt,
        system_prompt_file=system_prompt_file,
        # Bash included: sonnet 4.6 strongly prefers writing judge_prompt.json
        # via a heredoc/python one-liner. Without Bash the write is denied and
        # no rubric file lands on disk, so the static check fails and every
        # retry re-loses the same way. Granting Bash lets the model's preferred
        # write path succeed on the first attempt. Content/quality unchanged.
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
        effort=effort,
        resume_session_id=resume_session_id,
    )

    # Even if the CLI reports non-zero exit / is_error (e.g. it ran out of turns
    # after writing the file via Bash), the rubric's real product is the on-disk
    # judge_prompt.json. Let the static checks below be the source of truth.
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    if not out.ok and not judge_path.exists():
        return out

    issues = _static_checks(judge_path, case_dir)
    if issues:
        out.ok = False
        out.error = "judge_prompt static checks: " + "; ".join(issues[:6])
    else:
        # Valid rubric on disk -> stage succeeded regardless of CLI exit code.
        out.ok = True
        out.error = None
    return out
