"""Stage 1: DocProfile — read the PDF, produce _doc_card.json.

Validates output against doc_card.schema.json and writes research_notes.md.
Domain context is injected via DomainPack → prompt_compose.
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
Stage 1: 文档画像（DocProfile）。

当前工作目录中的输入：
- ./material.pdf — 要分析的文档 PDF。
- ./_doc_card.schema.json — 由管线挂载的 DocCard JSON Schema。

按照系统提示中的流程执行：
1. 仔细阅读 material.pdf（Pass A: 第1页；Pass B: 完整正文；
   Pass C: 关键数据与术语；Pass D: 陷阱猎捕）。
2. 填写 DocCard 的每个必需字段（参考领域上下文中的文档类型提示）。
3. 使用 Write 工具将结果保存到 ./_doc_card.json。
4. 最终助手消息中，仅输出你写入的同一 JSON 对象（无文字说明，无围栏）。
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    schema_src = SCHEMAS_DIR / "doc_card.schema.json"
    schema_dst = case_dir / "_doc_card.schema.json"
    schema_dst.write_bytes(schema_src.read_bytes())
    # Also write the legacy name so any references to _paper_card.schema.json still work
    legacy_dst = case_dir / "_paper_card.schema.json"
    legacy_dst.write_bytes(schema_src.read_bytes())


def _load_schema() -> dict:
    return json.loads((SCHEMAS_DIR / "doc_card.schema.json").read_text(encoding="utf-8"))


def _validate_doc_card(card: dict) -> list[str]:
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(card), key=lambda e: list(e.path))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors]


def _write_research_notes(case_dir: Path, card: dict) -> None:
    lines: list[str] = []
    lines.append(f"# 文档分析笔记 — {card.get('title', '<未知标题>')}\n")
    lines.append("## 元数据\n")
    lines.append(f"- 作者/主讲: {card.get('authors', '?')}")
    lines.append(f"- 单位: {card.get('affiliation', '?')}")
    lines.append(f"- 场合: {card.get('source_event', card.get('conference', '?'))}")
    lines.append(f"- 一级领域: {card.get('primary_domain', '?')}")
    lines.append(f"- 二级领域: {card.get('sub_domain', '?')}")
    lines.append(f"- 文档类型: {card.get('document_type', '?')}")
    lines.append(f"- PDF 页数: {card.get('pdf_pages', '?')}")
    pcr = card.get("page_count_range") or [12, 16]
    lines.append(f"- 幻灯片页数范围: {pcr[0]}-{pcr[1]}")
    lines.append("")
    lines.append("## 核心主张")
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
    max_turns: int = 50,
    timeout_s: int = 1800,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
    domain_pack: DomainPack | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    base_system = PROMPTS_DIR / "1_profile_system.md"
    system_prompt_file = compose("1_profile", base_system, case_dir, domain_pack)

    out = await run_stage(
        stage_name="1_profile",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )
    if not out.ok:
        return out

    # Accept either _doc_card.json or _paper_card.json (legacy compat)
    card_path = case_dir / "_doc_card.json"
    if not card_path.exists():
        legacy = case_dir / "_paper_card.json"
        if legacy.exists():
            card_path = legacy

    card: dict | None = None
    if card_path.exists():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            out.ok = False
            out.error = f"_doc_card.json present but unparseable: {e}"
            return out

    if card is None:
        card = extract_final_json(out.raw_result)
        if card is None:
            out.ok = False
            out.error = "no _doc_card.json on disk and no parseable JSON in final message"
            return out
        card_path = case_dir / "_doc_card.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ensure canonical filename
    canonical = case_dir / "_doc_card.json"
    if card_path != canonical:
        canonical.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    # Also write legacy _paper_card.json for stage3/4 compat (they read it for field manifest)
    legacy_path = case_dir / "_paper_card.json"
    if not legacy_path.exists():
        legacy_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")

    errors = _validate_doc_card(card)
    if errors:
        out.ok = False
        out.error = "doc_card schema violations: " + "; ".join(errors[:5])
        return out

    try:
        _write_research_notes(case_dir, card)
    except Exception as e:  # noqa: BLE001
        out.parsed_payload = (out.parsed_payload or {}) | {
            "research_notes_warning": str(e),
        }

    return out
