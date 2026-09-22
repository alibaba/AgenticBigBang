"""Stage 1: PaperProfile — read the PDF, produce _paper_card.json.

Validates the agent's output against the JSON Schema and writes
``research_notes.md`` (a human-readable derivative of the Paper Card).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore

from ._runner import StageOutcome, run_stage, extract_final_json

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


_USER_PROMPT = """\
Stage 1: 论文画像。

论文 PDF 位于当前工作目录的 ./material.pdf。Paper Card JSON Schema 位于
./_paper_card.schema.json（由管线挂载）。

按照系统提示中的流程执行：
1. 仔细阅读 material.pdf（Pass A: 第 1-2 页；Pass B: 完整正文；
   Pass C: 术语与细节；Pass D: 陷阱猎捕）。
2. 填写 Paper Card 的每个必需字段。
3. 使用 Write 工具将结果保存到 ./_paper_card.json。
4. 最终助手消息中，仅输出你写入的同一 JSON 对象（无文字说明，无围栏）。
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "paper_card.schema.json"
    schema_dst = case_dir / "_paper_card.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())


def _load_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "paper_card.schema.json").read_text(encoding="utf-8"))


def _validate_paper_card(card: dict) -> list[str]:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(card), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]


def _write_research_notes(case_dir: Path, card: dict) -> None:
    lines: list[str] = []
    lines.append(f"# 研究笔记 — {card.get('title', '<未知标题>')}\n")
    lines.append("## 元数据\n")
    lines.append(f"- 作者: {card.get('authors', '?')}")
    lines.append(f"- 单位: {card.get('affiliation', '?')}")
    lines.append(f"- 会议: {card.get('conference', '?')}")
    lines.append(f"- 领域: {card.get('domain', '?')}")
    lines.append(f"- 论文类型: {card.get('paper_type', '?')}")
    lines.append(f"- PDF 页数: {card.get('pdf_pages', '?')}")
    pcr = card.get("page_count_range") or [16, 20]
    lines.append(f"- 幻灯片页数范围: {pcr[0]}-{pcr[1]}")
    lines.append("")
    lines.append("## 核心论点")
    lines.append(card.get("central_thesis", ""))
    lines.append("")
    lines.append("## 章节结构")
    for i, sec in enumerate(card.get("ordered_sections") or [], 1):
        lines.append(f"{i}. **{sec.get('title')}** ({sec.get('kind')})")
        for b in sec.get("bullets", []) or []:
            lines.append(f"    - {b}")
        if sec.get("design_constraint"):
            lines.append(f"    - _设计约束:_ {sec['design_constraint']}")
    lines.append("")
    lines.append("## 关键数据")
    for n in card.get("key_numbers", []) or []:
        anchor = f" ({n['paper_anchor']})" if n.get("paper_anchor") else ""
        lines.append(f"- {n['claim']}{anchor}")
    lines.append("")
    lines.append("## 关键图表")
    for f in card.get("key_figures", []) or []:
        page = f" p.{f['page']}" if f.get("page") else ""
        slide = f" → {f['intended_slide']}" if f.get("intended_slide") else ""
        lines.append(f"- **{f['id']}**{page}: {f['what']}{slide}")
    lines.append("")
    lines.append("## 关键术语")
    for t in card.get("key_terms", []) or []:
        cc = f"\n    - 常见混淆: {t['common_confusion']}" if t.get("common_confusion") else ""
        lines.append(f"- **{t['term']}**: {t['definition']}{cc}")
    lines.append("")
    lines.append("## 陷阱")
    for tr in card.get("traps", []) or []:
        lines.append(f"- _{tr['kind']}_: 避免 \"{tr['claim_to_avoid']}\"; 正确: \"{tr['correct_form']}\"")
    lines.append("")
    (case_dir / "research_notes.md").write_text("\n".join(lines), encoding="utf-8")


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 25,
    timeout_s: int = 1800,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    system_prompt_file = PROMPTS_DIR / "1_profile_system.md"
    out = await run_stage(
        stage_name="1_profile",
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

    card_path = case_dir / "_paper_card.json"
    card: dict | None = None
    if card_path.exists():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            out.ok = False
            out.error = f"_paper_card.json present but unparseable: {e}"
            return out

    if card is None:
        card = extract_final_json(out.raw_result)
        if card is None:
            out.ok = False
            out.error = "no _paper_card.json on disk and no parseable JSON in final message"
            return out
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    errors = _validate_paper_card(card)
    if errors:
        out.ok = False
        out.error = "paper_card schema violations: " + "; ".join(errors[:5])
        return out

    try:
        _write_research_notes(case_dir, card)
    except Exception as e:  # noqa: BLE001
        out.parsed_payload = (out.parsed_payload or {}) | {
            "research_notes_warning": str(e),
        }

    return out
