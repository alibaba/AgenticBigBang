"""Stage 4b: 条件式验证-精修（中文适配）。

仅当 Stage 4 审计评分触发时运行（锚点特定性、trap 覆盖、原子性或
key_numbers 覆盖的低分）。执行逐项区分力评估、trap 覆盖交叉检查、
定向修订、去重和抽检——全部在一次 LLM 调用中完成。

退化保护：若 C1 或 C2 数量下降 >20%，回退到修订前版本。
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
    r"\bFigure\s+\d+|\bTable\s+\d+|\bFig\.\s*\d+|图\s*\d+|表\s*\d+",
    re.IGNORECASE,
)


def should_trigger(audit_scores: dict[str, int]) -> tuple[bool, list[str]]:
    if not audit_scores:
        return False, []
    low_axes = [
        ax for ax, score in audit_scores.items()
        if isinstance(score, int) and score <= 3
    ]
    trigger = bool(_CRITICAL_AXES & set(low_axes)) or len(low_axes) >= 3
    return trigger, low_axes


_USER_PROMPT_TEMPLATE = """\
Stage 4b: 验证-精修（条件触发）。

本案例因以下审计轴评分 ≤3 而触发验证-精修: {low_axes_str}

当前评分标准有 {pre_c1} 项 C1 和 {pre_c2} 项 C2。

退化约束: 修订后 C1 不得低于 {min_c1}，C2 不得低于 {min_c2}。
不要合并评分 3-5 的项。仅评分 1-2 的项可删除、改写或拆分。
有疑问时，保留原项。

当前工作目录中的输入：
- ./generation_task/judge_prompt.json（待评估和修订的评分标准）
- ./_paper_card.json（真实来源）
- ./_field_manifest.txt（必覆盖清单）
- ./_audit_report.json（触发本步骤的审计报告）
- ./_verify_refine_trigger.json（触发上下文：哪些轴失败及原因）
- ./_verify_refine_report.schema.json（输出报告的 schema）

按系统提示中的 5 项任务执行（区分力评分、traps 交叉检查、内联
修订、去重、抽检）。原地编辑 judge_prompt.json。然后写入
./_verify_refine_report.json 并将同一 JSON 作为最终消息输出
（无文字说明，无 markdown 围栏）。
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "verify_refine_report.schema.json"
    schema_dst = case_dir / "_verify_refine_report.schema.json"
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


_MAX_COUNT_DROP_RATIO = 0.20


def _get_rubric_counts(path: Path) -> tuple[int, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        c1 = data.get("material_dependent_checklist_1") or []
        c2 = data.get("material_dependent_checklist_2") or []
        return len(c1), len(c2)
    except (json.JSONDecodeError, OSError):
        return 0, 0


def _get_rubric_items(path: Path) -> tuple[list[str], list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        c1 = data.get("material_dependent_checklist_1") or []
        c2 = data.get("material_dependent_checklist_2") or []
        return c1, c2
    except (json.JSONDecodeError, OSError):
        return [], []


def _write_trigger_context(case_dir: Path, low_axes: list[str]) -> None:
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
            f"聚焦于 low_axes 中列出的轴进行修订。"
            f"这些轴的低分项是改进的最高优先目标。"
            f"关键：修订后 C1 数量不得低于 "
            f"{max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO)))} "
            f"（当前: {pre_c1}），C2 数量不得低于 "
            f"{max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO)))} "
            f"（当前: {pre_c2}）。"
            "不要合并评分 3-5 的项。仅删除/改写评分 1-2 的项。"
        ),
    }
    (case_dir / "_verify_refine_trigger.json").write_text(
        json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _backup_rubric(case_dir: Path) -> Path:
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    if judge_path.exists() and not backup_path.exists():
        shutil.copy2(judge_path, backup_path)
    return backup_path


def _restore_rubric_on_failure(case_dir: Path) -> None:
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    if backup_path.exists():
        shutil.copy2(backup_path, judge_path)


def _heal_judge_json(case_dir: Path) -> list[str]:
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
    schema = json.loads(
        (SCHEMAS_DIR / "verify_refine_report.schema.json").read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(report), key=lambda e: list(e.path))
    return [
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors
    ]


def _check_regression(case_dir: Path) -> list[str]:
    backup_path = case_dir / "_judge_prompt_pre_verify.json"
    judge_path = case_dir / "generation_task" / "judge_prompt.json"

    pre_c1, pre_c2 = _get_rubric_counts(backup_path)
    post_c1, post_c2 = _get_rubric_counts(judge_path)

    issues: list[str] = []
    if pre_c1 > 0 and post_c1 < max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO))):
        issues.append(
            f"C1 regression: {pre_c1} -> {post_c1} "
            f"(min {max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO)))})"
        )
    if pre_c2 > 0 and post_c2 < max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO))):
        issues.append(
            f"C2 regression: {pre_c2} -> {post_c2} "
            f"(min {max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO)))})"
        )
    return issues


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    low_axes: list[str],
    model: str | None = None,
    max_turns: int = 30,
    timeout_s: int = 1800,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    _write_trigger_context(case_dir, low_axes)
    _backup_rubric(case_dir)

    judge_path = case_dir / "generation_task" / "judge_prompt.json"
    pre_c1, pre_c2 = _get_rubric_counts(judge_path)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        low_axes_str=", ".join(low_axes),
        pre_c1=pre_c1,
        pre_c2=pre_c2,
        min_c1=max(9, int(pre_c1 * (1 - _MAX_COUNT_DROP_RATIO))),
        min_c2=max(8, int(pre_c2 * (1 - _MAX_COUNT_DROP_RATIO))),
    )

    system_prompt_file = PROMPTS_DIR / "verify_refine_system.md"
    out = await run_stage(
        stage_name="4b_verify_refine",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=user_prompt,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )

    if not out.ok:
        _restore_rubric_on_failure(case_dir)
        return out

    heal_issues = _heal_judge_json(case_dir)
    if heal_issues:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = "post-VR JSON healing failed: " + "; ".join(heal_issues)
        return out

    regression_issues = _check_regression(case_dir)
    if regression_issues:
        _restore_rubric_on_failure(case_dir)
        out.ok = False
        out.error = "VR regression detected, reverted: " + "; ".join(regression_issues)
        return out

    report_path = case_dir / "_verify_refine_report.json"
    report: dict | None = None
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    if report is None:
        report = extract_final_json(out.raw_result)
        if report:
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    if report:
        schema_errors = _validate_report(report)
        if schema_errors:
            out.parsed_payload = (out.parsed_payload or {}) | {
                "verify_refine_schema_warnings": schema_errors[:5],
            }

    return out
