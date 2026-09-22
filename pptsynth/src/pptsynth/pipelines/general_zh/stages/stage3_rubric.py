"""Stage 3: Author judge_prompt.json — completeness + correctness checklists.

AB2 improvements: manifest-first, content-driven item count, contrastive anchors,
atomicity, boilerplate suppression, few-shot.
Domain context injected via DomainPack.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ._runner import StageOutcome, run_stage
from ..domain_registry import DomainPack
from ..prompt_compose import compose

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PKG_DIR = Path(__file__).resolve().parent.parent

_USER_PROMPT = """\
Stage 3: 撰写评分标准（Judge Rubric）。

当前工作目录中的输入：
- ./_doc_card.json（或 _paper_card.json）
- ./_field_manifest.txt（自动生成——列出所有必须覆盖的字段）
- ./generation_task/instructions.md

首先阅读 _field_manifest.txt。它列出了每个 key_number、trap 和
confusable key_term——你必须全部覆盖。以建议项数为参考。

写一个文件 ./generation_task/judge_prompt.json，仅包含两个键：
material_dependent_checklist_1（完整性项）和
material_dependent_checklist_2（正确性项）。

项数由文档内容驱动（见 manifest 的建议数量）。不要强制固定项数——
让文档的 key_numbers、traps 和 key_terms 决定需要多少项。

匹配官方 PPTSynth 中文检查列表风格：每项是一个 Markdown 格式字符串，
以换行符开头和结尾，提出二元问题，带有具体的文档特定锚点。

写完后，输出一个 JSON 对象作为最终助手消息：
{"stage":"rubric","ok":true,"completeness_count":<int>,"correctness_count":<int>,"anchors_extracted_from_doc_card":<int>,"key_numbers_covered":<int>,"traps_covered":<int>,"confusable_terms_covered":<int>,"warnings":[]}
"""

_FIGURE_REF_RE = re.compile(r"\b(?:图|表|Figure|Table|Fig\.)\s*\d+", re.IGNORECASE)


def _generate_field_manifest(case_dir: Path) -> None:
    from ..extract_field_manifest import build_manifest

    # Prefer doc_card, fall back to paper_card
    pc_path = case_dir / "_doc_card.json"
    if not pc_path.exists():
        pc_path = case_dir / "_paper_card.json"
    if not pc_path.exists():
        return
    pc = json.loads(pc_path.read_text(encoding="utf-8"))
    manifest = build_manifest(pc)
    (case_dir / "_field_manifest.txt").write_text(manifest, encoding="utf-8")


def _repair_json(raw: str, path: Path) -> dict | None:
    """Try to repair a JSON string and write the repaired version to disk.

    Returns the parsed dict on success, or None if repair fails.
    """
    try:
        from json_repair import repair_json  # type: ignore
        repaired = repair_json(raw)
        data = json.loads(repaired)
        if isinstance(data, dict):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
    except Exception:  # noqa: BLE001
        pass
    return None


def _static_checks(judge_path: Path, case_dir: Path) -> list[str]:
    issues: list[str] = []
    if not judge_path.exists():
        return ["judge_prompt.json not on disk"]
    raw = judge_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try auto-repair before giving up
        data = _repair_json(raw, judge_path)
        if data is None:
            return [f"judge_prompt.json invalid JSON (repair failed)"]
    if not isinstance(data, dict):
        return ["judge_prompt.json root is not an object"]
    # Accept either naming convention
    c1 = data.get("material_dependent_checklist_1") or data.get("completeness_checklist") or []
    c2 = data.get("material_dependent_checklist_2") or data.get("correctness_checklist") or []
    if not c1 and not c2:
        expected = {"material_dependent_checklist_1", "material_dependent_checklist_2"}
        issues.append(f"missing checklist keys; expected {expected}; got {sorted(data.keys())}")
    if not isinstance(c1, list) or not isinstance(c2, list):
        issues.append("checklist values must be arrays")
        return issues
    if not (9 <= len(c1) <= 40):
        issues.append(f"completeness count out of [9,40]: {len(c1)}")
    if not (8 <= len(c2) <= 45):
        issues.append(f"correctness count out of [8,45]: {len(c2)}")
    for i, item in enumerate(c1, 1):
        if not isinstance(item, str):
            issues.append(f"completeness[{i}] not a string"); continue
        if "?" not in item and "？" not in item:
            issues.append(f"completeness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"completeness[{i}] missing bold question marker")
        if len(item) > 600:
            issues.append(f"completeness[{i}] too long ({len(item)} chars)")
    for i, item in enumerate(c2, 1):
        if not isinstance(item, str):
            issues.append(f"correctness[{i}] not a string"); continue
        if "?" not in item and "？" not in item:
            issues.append(f"correctness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"correctness[{i}] missing bold question marker")
        if "如果**否**" not in item and "If **no**" not in item:
            issues.append(f"correctness[{i}] missing '如果**否**' instruction")
        if len(item) > 600:
            issues.append(f"correctness[{i}] too long ({len(item)} chars)")

    # Check figure/table reference ratio
    all_items = c1 + c2
    fig_ref_count = sum(1 for item in all_items if _FIGURE_REF_RE.search(item))
    if all_items and fig_ref_count > len(all_items) * 0.15:
        issues.append(
            f"{fig_ref_count}/{len(all_items)} items reference Figure/Table/图/表 "
            f"numbers — describe CONTENT instead"
        )

    # Trap coverage is evaluated by Stage 4 audit (trap_coverage axis); skip here.

    return issues


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
    _generate_field_manifest(case_dir)
    base_system = PROMPTS_DIR / "3_rubric_system.md"
    system_prompt_file = compose("3_rubric", base_system, case_dir, domain_pack)

    out = await run_stage(
        stage_name="3_rubric",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )
    if not out.ok:
        return out

    issues = _static_checks(
        case_dir / "generation_task" / "judge_prompt.json",
        case_dir,
    )
    if issues:
        out.ok = False
        out.error = "judge_prompt static checks: " + "; ".join(issues[:6])
    return out
