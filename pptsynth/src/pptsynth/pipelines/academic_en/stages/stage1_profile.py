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
Stage 1: Paper Profile.

The paper PDF is at ./material.pdf in this working directory. The Paper
Card JSON Schema is at ./_paper_card.schema.json (mounted by the harness).

Follow the procedure in your system prompt:
1. Read material.pdf carefully (Pass A: pages 1-2; Pass B: full body;
   Pass C: specifics; Pass D: trap hunt).
2. Fill every required field in the Paper Card.
3. Use the Write tool to save the result to ./_paper_card.json.
4. As your final assistant message, emit only the same JSON object you
   wrote (no prose, no fences).
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    """Mount schema and the system prompt reference files into the case dir.

    We copy (not symlink) so that ``--bare`` + cwd isolation actually keeps
    the model's view limited to the case directory.
    """
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
    """A short human-readable summary, derived deterministically from the card.

    research_notes.md is *for humans*. It is not consumed by downstream
    stages.
    """
    lines: list[str] = []
    lines.append(f"# Research Notes — {card.get('title', '<unknown title>')}\n")
    lines.append("## Metadata\n")
    lines.append(f"- Authors: {card.get('authors', '?')}")
    lines.append(f"- Affiliation: {card.get('affiliation', '?')}")
    lines.append(f"- Conference: {card.get('conference', '?')}")
    lines.append(f"- PDF pages: {card.get('pdf_pages', '?')}")
    pcr = card.get("page_count_range") or [16, 20]
    lines.append(f"- Slide range: {pcr[0]}-{pcr[1]}")
    lines.append("")
    lines.append("## Central Thesis")
    lines.append(card.get("central_thesis", ""))
    lines.append("")
    lines.append("## Ordered Sections")
    for i, sec in enumerate(card.get("ordered_sections") or [], 1):
        lines.append(f"{i}. **{sec.get('title')}** ({sec.get('kind')})")
        for b in sec.get("bullets", []) or []:
            lines.append(f"    - {b}")
        if sec.get("design_constraint"):
            lines.append(f"    - _Design Constraint:_ {sec['design_constraint']}")
    lines.append("")
    lines.append("## Key Numbers")
    for n in card.get("key_numbers", []) or []:
        anchor = f" ({n['paper_anchor']})" if n.get("paper_anchor") else ""
        lines.append(f"- {n['claim']}{anchor}")
    lines.append("")
    lines.append("## Key Figures")
    for f in card.get("key_figures", []) or []:
        page = f" p.{f['page']}" if f.get("page") else ""
        slide = f" → {f['intended_slide']}" if f.get("intended_slide") else ""
        lines.append(f"- **{f['id']}**{page}: {f['what']}{slide}")
    lines.append("")
    lines.append("## Key Terms")
    for t in card.get("key_terms", []) or []:
        cc = f"\n    - common confusion: {t['common_confusion']}" if t.get("common_confusion") else ""
        lines.append(f"- **{t['term']}**: {t['definition']}{cc}")
    lines.append("")
    lines.append("## Traps")
    for tr in card.get("traps", []) or []:
        lines.append(f"- _{tr['kind']}_: avoid \"{tr['claim_to_avoid']}\"; correct: \"{tr['correct_form']}\"")
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
        allowed_tools=["Read", "Write", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )

    if not out.ok:
        return out

    # Prefer the file the model wrote on disk; fall back to the JSON in the
    # final message if the file is missing.
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

    # Derive the human-readable research_notes.md
    try:
        _write_research_notes(case_dir, card)
    except Exception as e:  # noqa: BLE001
        # research_notes is non-blocking
        out.parsed_payload = (out.parsed_payload or {}) | {
            "research_notes_warning": str(e),
        }

    return out
