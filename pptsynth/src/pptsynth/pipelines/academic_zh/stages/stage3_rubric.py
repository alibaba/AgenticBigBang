"""Stage 3: 编写 judge_prompt.json — 完整性 + 正确性检查列表。

合并自 refineAB2（manifest-first、content-driven counts、图号检测、
trap 覆盖检查）和 sinoconf_v3（中文 prompt/静态检查）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ._runner import StageOutcome, run_stage

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PKG_DIR = Path(__file__).resolve().parent.parent

_USER_PROMPT = """\
Stage 3: 编写评判评分标准。

当前工作目录中的输入：
- ./_paper_card.json
- ./_field_manifest.txt（自动生成——列出你必须覆盖的所有字段）
- ./generation_task/instructions.md

先阅读 _field_manifest.txt。它列出了你必须覆盖的每个 key_number、
trap 和易混淆 key_term。使用建议的检查项数量作为参考。

写一个文件 ./generation_task/judge_prompt.json，恰好含两个键：
material_dependent_checklist_1（完整性检查项）和
material_dependent_checklist_2（正确性检查项）。

检查项数量由论文内容驱动（参见清单中的建议数量）。不要强制固定
数量——让论文的 key_numbers、traps 和 key_terms 决定需要多少项。

匹配官方 PPTSynth 学术检查列表风格：每项是一个以换行开头和结尾的
Markdown 格式字符串，以二元判断问题形式呈现，附带论文特定的具体锚点。

写完后，输出一个 JSON 对象作为最终助手消息：
{"stage":"rubric","ok":true,"completeness_count":<int>,"correctness_count":<int>,"anchors_extracted_from_paper_card":<int>,"key_numbers_covered":<int>,"traps_covered":<int>,"confusable_terms_covered":<int>,"warnings":[]}
"""

_FIGURE_REF_RE = re.compile(
    r"\bFigure\s+\d+|\bTable\s+\d+|\bFig\.\s*\d+|图\s*\d+|表\s*\d+",
    re.IGNORECASE,
)


def _generate_field_manifest(case_dir: Path) -> None:
    from ..extract_field_manifest import build_manifest

    pc_path = case_dir / "_paper_card.json"
    if not pc_path.exists():
        return
    pc = json.loads(pc_path.read_text(encoding="utf-8"))
    manifest = build_manifest(pc)
    (case_dir / "_field_manifest.txt").write_text(manifest, encoding="utf-8")


def _static_checks(judge_path: Path, case_dir: Path | None = None) -> list[str]:
    issues: list[str] = []
    if not judge_path.exists():
        return ["judge_prompt.json not on disk"]
    try:
        data = json.loads(judge_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"judge_prompt.json invalid JSON: {e}"]

    expected_keys = {"material_dependent_checklist_1", "material_dependent_checklist_2"}
    if set(data.keys()) != expected_keys:
        issues.append(f"unexpected keys: {sorted(data.keys())}")
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
        if "？" not in item and "?" not in item:
            issues.append(f"completeness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"completeness[{i}] missing bold question marker")
        if len(item) > 550:
            issues.append(f"completeness[{i}] too long ({len(item)} chars)")
    for i, item in enumerate(c2, 1):
        if not isinstance(item, str):
            issues.append(f"correctness[{i}] not a string")
            continue
        if "？" not in item and "?" not in item:
            issues.append(f"correctness[{i}] has no question mark")
        if "**" not in item:
            issues.append(f"correctness[{i}] missing bold question marker")
        if "如果**否**" not in item and "如果 **否**" not in item and "若**否**" not in item and "If **no**" not in item:
            issues.append(f"correctness[{i}] missing '如果**否**' instruction")
        if len(item) > 550:
            issues.append(f"correctness[{i}] too long ({len(item)} chars)")

    all_items = c1 + c2
    fig_ref_count = sum(1 for item in all_items if _FIGURE_REF_RE.search(item))
    if fig_ref_count > len(all_items) * 0.15:
        issues.append(
            f"{fig_ref_count}/{len(all_items)} items reference Figure/Table "
            f"numbers — describe CONTENT instead"
        )

    if case_dir is not None:
        pc_path = case_dir / "_paper_card.json"
        if pc_path.exists():
            try:
                pc = json.loads(pc_path.read_text(encoding="utf-8"))
                traps = pc.get("traps") or []
                c2_text = " ".join(c2).lower()

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


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 20,
    timeout_s: int = 1200,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    _generate_field_manifest(case_dir)

    system_prompt_file = PROMPTS_DIR / "3_rubric_system.md"
    out = await run_stage(
        stage_name="3_rubric",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
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
