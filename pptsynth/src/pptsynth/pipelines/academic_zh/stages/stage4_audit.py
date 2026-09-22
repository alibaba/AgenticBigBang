"""Stage 4: 审计与自动修复。

11轴审计（合并自 refineAB2 的 atomicity_check/key_numbers_coverage
和 sinoconf_v3 的中文适配）。审计编辑后重跑 Stage 2/3 静态检查。
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore

from ._runner import StageOutcome, run_stage, extract_final_json

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

_USER_PROMPT = """\
Stage 4: 审计与自动修复。

当前工作目录中的输入：
- ./material.pdf（尽量少读；使用 `pages` 参数）
- ./_paper_card.json
- ./_field_manifest.txt（自动生成的必覆盖清单）
- ./generation_task/instructions.md
- ./generation_task/judge_prompt.json
- ./_audit_report.schema.json

按照系统提示中的 11 轴评分标准评分。仅应用允许的就地修复。
然后写入 ./_audit_report.json（须通过 schema 校验）并将同一 JSON
对象作为最终助手消息输出（无文字说明，无 markdown 围栏）。
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "audit_report.schema.json"
    schema_dst = case_dir / "_audit_report.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())

    manifest_path = case_dir / "_field_manifest.txt"
    pc_path = case_dir / "_paper_card.json"
    if not manifest_path.exists() and pc_path.exists():
        try:
            from ..extract_field_manifest import build_manifest
            pc = json.loads(pc_path.read_text(encoding="utf-8"))
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
        allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )
    if not out.ok:
        return out

    report_path = case_dir / "_audit_report.json"
    report: dict | None = None
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            out.ok = False
            out.error = f"_audit_report.json present but unparseable: {e}"
            return out
    if report is None:
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

    from .stage2_task import _static_checks as instructions_static_checks
    from .stage3_rubric import _static_checks as rubric_static_checks

    instr_issues = instructions_static_checks(case_dir / "generation_task" / "instructions.md")
    rubric_issues = rubric_static_checks(case_dir / "generation_task" / "judge_prompt.json", case_dir)
    post_edit_issues = instr_issues + rubric_issues

    if post_edit_issues:
        out.ok = False
        out.error = "post-audit static checks failed: " + "; ".join(post_edit_issues[:5])
        return out

    out.parsed_payload = (out.parsed_payload or {}) | {
        "audit_pass": bool(report.get("pass")),
        "audit_scores": report.get("scores"),
    }
    return out
