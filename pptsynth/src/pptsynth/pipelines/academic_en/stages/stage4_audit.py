"""Stage 4: Audit and Auto-Fix.

The agent reads the case, scores along 11 axes (9 original + atomicity_check
+ key_numbers_coverage), fixes what it can in place, and returns a structured
audit_report.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore

from ._runner import StageOutcome, run_stage, extract_final_json

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

_USER_PROMPT = """\
Stage 4: Audit and Auto-Fix.

Inputs in this working directory:
- ./material.pdf (read sparingly; use the `pages` parameter)
- ./_paper_card.json
- ./_field_manifest.txt (auto-generated mandatory coverage manifest)
- ./generation_task/instructions.md
- ./generation_task/judge_prompt.json
- ./_audit_report.schema.json

Score the case along the 11 axes in your system prompt. Apply only the
permitted in-place fixes. Then write ./_audit_report.json that validates
against the schema and emit the same JSON object as your final assistant
message (no prose, no markdown fences).

Pay special attention to the two new axes: atomicity_check (each item
tests exactly one condition) and key_numbers_coverage (correctness items
reference >=80% of key_numbers). Cross-check against _field_manifest.txt
for coverage gaps.
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "audit_report.schema.json"
    schema_dst = case_dir / "_audit_report.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())

    # Ensure field manifest exists (normally created by stage 3, but
    # regenerate if missing — e.g. when resuming from a prior run).
    manifest_path = case_dir / "_field_manifest.txt"
    pc_path = case_dir / "_paper_card.json"
    if not manifest_path.exists() and pc_path.exists():
        try:
            from ..extract_field_manifest import build_manifest
            import json as _json
            pc = _json.loads(pc_path.read_text(encoding="utf-8"))
            manifest_path.write_text(build_manifest(pc), encoding="utf-8")
        except Exception:
            pass


def _validate_audit(report: dict) -> list[str]:
    schema = json.loads((SCHEMAS_DIR / "audit_report.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 30,
    timeout_s: int = 1500,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    system_prompt_file = PROMPTS_DIR / "4_audit_system.md"
    out = await run_stage(
        stage_name="4_audit",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        # Bash included: sonnet 4.6 prefers writing _audit_report.json via a
        # heredoc/python one-liner; without Bash it burns turns on denied calls
        # before falling back. Granting it lets the write succeed directly.
        allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )
    # Salvage a completed audit even when the CLI reports a non-zero exit or
    # is_error (commonly: the model wastes turns trying the disallowed Bash tool
    # to write the report, hits max_turns, and exits 1 — *after* it already
    # wrote a valid ./_audit_report.json via the Write tool). The audit's real
    # product is the on-disk report + in-place rubric fixes; if that report
    # exists and passes schema, the stage succeeded regardless of exit code.
    # This avoids discarding good work and re-running the expensive stage on
    # retries (which just re-trigger the same benign failure).
    report_path = case_dir / "_audit_report.json"
    report: dict | None = None
    if report_path.exists():
        try:
            candidate = json.loads(report_path.read_text(encoding="utf-8"))
            if not _validate_audit(candidate):
                report = candidate  # schema-valid report on disk -> salvage
        except json.JSONDecodeError:
            report = None

    if report is None:
        # No salvageable report file. Fall back to the run outcome and the
        # model's final assistant message.
        if not out.ok:
            return out
        report = extract_final_json(out.raw_result)
        if report is None:
            out.ok = False
            out.error = "audit produced no parseable report"
            return out
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        errors = _validate_audit(report)
        if errors:
            out.ok = False
            out.error = "audit_report schema violations: " + "; ".join(errors[:5])
            return out

    # A valid report exists (either salvaged from disk or freshly written).
    out.ok = True
    out.error = None
    out.parsed_payload = (out.parsed_payload or {}) | {
        "audit_pass": bool(report.get("pass")),
        "audit_scores": report.get("scores"),
    }
    return out
