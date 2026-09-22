"""Stage 4: Audit and Auto-Fix.

11-axis audit (same as AB2: 9 original + atomicity_check + key_numbers_coverage).
Adds post-audit static recheck (from sinoconf v3).
Domain context injected via DomainPack.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore

from ._runner import StageOutcome, run_stage, extract_final_json
from ..domain_registry import DomainPack
from ..prompt_compose import compose

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"

_USER_PROMPT = """\
Stage 4: 审计与自动修复。

当前工作目录中的输入：
- ./material.pdf（尽量少读；使用 pages 参数）
- ./_doc_card.json（或 _paper_card.json）
- ./_field_manifest.txt（自动生成的强制覆盖清单）
- ./generation_task/instructions.md
- ./generation_task/judge_prompt.json
- ./_audit_report.schema.json

按照系统提示中的 11 轴评分标准评分。仅应用允许的就地修复。
特别注意 atomicity_check 和 key_numbers_coverage 两个新轴。
对照 _field_manifest.txt 检查覆盖缺口。

然后写入 ./_audit_report.json（须通过 schema 校验）并将同一 JSON
对象作为最终助手消息输出（无文字说明，无 markdown 围栏）。
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "audit_report.schema.json"
    schema_dst = case_dir / "_audit_report.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())

    manifest_path = case_dir / "_field_manifest.txt"
    pc_path = case_dir / "_doc_card.json"
    if not pc_path.exists():
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
    domain_pack: DomainPack | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    base_system = PROMPTS_DIR / "4_audit_system.md"
    system_prompt_file = compose("4_audit", base_system, case_dir, domain_pack)

    out = await run_stage(
        stage_name="4_audit",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Edit", "Write", "Glob", "Grep"],
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
        raw = report_path.read_text(encoding="utf-8")
        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            # Try auto-repair (unescaped quotes in LLM-generated JSON)
            try:
                from json_repair import repair_json  # type: ignore
                repaired = repair_json(raw)
                report = json.loads(repaired)
                if isinstance(report, dict):
                    report_path.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                else:
                    report = None
            except Exception:
                report = None
            if report is None:
                out.ok = False
                out.error = "_audit_report.json present but unparseable (repair failed)"
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

    # Post-audit static recheck (lightweight — only critical structural issues)
    from .stage2_task import _static_checks as instructions_static_checks
    from .stage3_rubric import _repair_json

    instr_issues = instructions_static_checks(
        case_dir / "generation_task" / "instructions.md",
        domain_pack=domain_pack,
    )
    # For judge_prompt: only check parsability and minimal structure (no count/coverage limits)
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    rubric_issues: list[str] = []
    if not judge_path.exists():
        rubric_issues.append("judge_prompt.json not on disk after audit")
    else:
        raw = judge_path.read_text(encoding="utf-8")
        try:
            jdata = json.loads(raw)
        except json.JSONDecodeError:
            jdata = _repair_json(raw, judge_path)
            if jdata is None:
                rubric_issues.append("judge_prompt.json invalid JSON after audit (repair failed)")
        if jdata is not None:
            # Accept either naming convention from LLM
            c1 = jdata.get("material_dependent_checklist_1") or jdata.get("completeness_checklist")
            c2 = jdata.get("material_dependent_checklist_2") or jdata.get("correctness_checklist")
            if not isinstance(c1, list):
                rubric_issues.append("judge_prompt missing completeness checklist")
            if not isinstance(c2, list):
                rubric_issues.append("judge_prompt missing correctness checklist")
            elif len(c2) < 8:
                rubric_issues.append(f"correctness count too low after audit: {len(c2)}")

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
