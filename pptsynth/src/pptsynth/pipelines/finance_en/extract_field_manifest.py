"""Extract a mandatory coverage manifest from _paper_card.json.

Reads a paper card and produces a structured Markdown manifest listing
all key_numbers, traps, and key_terms with common_confusion. This
manifest is injected into the Stage 3 rubric prompt to force the LLM
to reference every critical field.

Usage:
    python extract_field_manifest.py <paper_card.json> <output.txt>

Or programmatically:
    from extract_field_manifest import build_manifest
    text = build_manifest(paper_card_dict)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def build_manifest(pc: dict) -> str:
    key_numbers = pc.get("key_numbers") or []
    traps = pc.get("traps") or []
    key_terms = pc.get("key_terms") or []
    key_figures = pc.get("key_figures") or []

    confused_terms = [kt for kt in key_terms if kt.get("common_confusion")]

    lines: list[str] = []
    lines.append("## MANDATORY COVERAGE MANIFEST (auto-generated, do NOT ignore)\n")

    # Suggested item counts
    n_kf = len(key_figures)
    n_kn = len(key_numbers)
    suggested_c2 = 8 + math.ceil(n_kf * 0.5 + n_kn * 0.3)
    suggested_c1 = 3 + max(5, suggested_c2 - 8)
    lines.append(f"Suggested completeness item count: ~{suggested_c1} (3 always-required + {suggested_c1 - 3} paper-specific)")
    lines.append(f"Suggested correctness item count: ~{suggested_c2}")
    lines.append(f"(formula: 8 + ceil({n_kf} key_figures × 0.5 + {n_kn} key_numbers × 0.3))\n")

    # Key numbers
    lines.append(f"### key_numbers ({len(key_numbers)} entries — each MUST appear in at least one correctness item):\n")
    for i, kn in enumerate(key_numbers, 1):
        condition = kn.get("condition") or kn.get("paper_anchor") or ""
        cond_str = f' (anchor: "{condition}")' if condition else ""
        lines.append(f"- KN{i}: \"{kn['claim']}\"{cond_str}")
    lines.append("")

    # Traps
    lines.append(f"### traps ({len(traps)} entries — each MUST have a dedicated correctness item):\n")
    for i, t in enumerate(traps, 1):
        lines.append(f"- TRAP{i}: [{t['kind']}]")
        lines.append(f"    correct_form: \"{t['correct_form']}\"")
        lines.append(f"    claim_to_avoid: \"{t['claim_to_avoid']}\"")
    lines.append("")

    # Key terms with common_confusion
    if confused_terms:
        lines.append(f"### key_terms with common_confusion ({len(confused_terms)} entries — each MUST have a correctness item):\n")
        for i, kt in enumerate(confused_terms, 1):
            lines.append(f"- KT{i}: \"{kt['term']}\" confused_with=\"{kt['common_confusion']}\"")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <paper_card.json> <output.txt>", file=sys.stderr)
        return 2
    pc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(build_manifest(pc), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
