"""Stage 2: Render Instructions — Paper Card → instructions.md.

The boilerplate Sections 2-6 are mounted into the case dir so the agent can
copy them verbatim. Static checks confirm the result has the expected
shape, including Chinese anti-pre-disclosure patterns.

v3: Patterns imported from shared _anti_leakage module.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._runner import StageOutcome, run_stage
from .._anti_leakage import PRE_DISCLOSURE_PATTERNS, FORBIDDEN_META_TERMS

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_USER_PROMPT = """\
Stage 2: 渲染指令。

当前工作目录中的输入：
- ./_paper_card.json   — 论文特定内容的唯一数据源。
- ./_boilerplate_sections.md — 作为 Sections 2-6 原样粘贴。
- ./material.pdf       — 仅在消歧时打开；以 Paper Card 为准。

按照系统提示中描述的官方格式，写一个文件
./generation_task/instructions.md。

写完文件后，输出一个 JSON 对象作为最终助手消息：
{"stage":"task","ok":true,"section_count":<int>,"design_constraint_count":<int>,"byte_size":<int>,"warnings":[]}
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    boilerplate_src = PROMPTS_DIR / "boilerplate_sections.md"
    boilerplate_dst = case_dir / "_boilerplate_sections.md"
    boilerplate_dst.write_bytes(boilerplate_src.read_bytes())
    (case_dir / "generation_task").mkdir(parents=True, exist_ok=True)


def _section1_text(text: str) -> str:
    """Slice between '## 1. 内容要求' and the next '## ' heading."""
    start = text.find("## 1. 内容要求")
    if start < 0:
        return ""
    rest = text[start:]
    next_heading = re.search(r"\n## (?!1\. 内容要求)", rest)
    if next_heading:
        return rest[: next_heading.start()]
    return rest


def _static_checks(instructions_path: Path) -> list[str]:
    issues: list[str] = []
    if not instructions_path.exists():
        return ["instructions.md not on disk"]
    text = instructions_path.read_text(encoding="utf-8")
    if len(text) < 1500:
        issues.append(f"instructions.md too short ({len(text)} bytes)")
    required_phrases = [
        "幻灯片的严格约束",
        "## 1. 内容要求",
        "## 2. 内容约束",
        "## 3. 视觉与设计",
        "## 4. 文本质量",
        "## 5. 技术忠实性要求",
        "## 6. 演示风格与听众",
        "# **预期输出**",
    ]
    for ph in required_phrases:
        if ph not in text:
            issues.append(f"missing required section: {ph!r}")
    if "设计约束:" not in text and "设计约束：" not in text:
        issues.append("no 设计约束: lines (need >=3 across deck)")
    else:
        dc_count = text.count("设计约束:") + text.count("设计约束：")
        if dc_count < 2:
            issues.append(f"only {dc_count} 设计约束: lines (need >=2)")
    for term in FORBIDDEN_META_TERMS:
        if term in text:
            issues.append(f"forbidden meta term in instructions.md: {term!r}")
    for marker in ["论文标题:", "作者团队:", "单位:", "会议:"]:
        if marker not in text and marker.replace(":", "：") not in text:
            issues.append(f"title slide missing field: {marker!r}")
    if not re.search(r"必须包含 \*\*\d+-\d+ 页\*\*", text):
        issues.append("missing '必须包含 **N-M 页**' line")

    section1 = _section1_text(text)
    if section1:
        for pattern, label in PRE_DISCLOSURE_PATTERNS:
            hits = pattern.findall(section1)
            if hits:
                sample = hits[0] if isinstance(hits[0], str) else " ".join(hits[0])
                issues.append(
                    f"Section 1 pre-discloses values ({label}): {sample!r} "
                    f"({len(hits)} hit{'s' if len(hits) != 1 else ''}); "
                    "move specific values to the rubric, keep bullets topical"
                )
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
    _ensure_workspace_files(case_dir)
    system_prompt_file = PROMPTS_DIR / "2_task_system.md"
    out = await run_stage(
        stage_name="2_task",
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

    issues = _static_checks(case_dir / "generation_task" / "instructions.md")
    if issues:
        out.ok = False
        out.error = "instructions.md static checks: " + "; ".join(issues[:6])
    return out
