"""从 _paper_card.json 中提取必覆盖清单。

读取 Paper Card 并生成结构化 Markdown 清单，列出所有 key_numbers、
traps 和带 common_confusion 的 key_terms。此清单注入 Stage 3 rubric
prompt，强制 LLM 引用每个关键字段。

用法:
    python extract_field_manifest.py <paper_card.json> <output.txt>

或编程调用:
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
    lines.append("## 必覆盖清单（自动生成，不得忽略）\n")

    n_kf = len(key_figures)
    n_kn = len(key_numbers)
    suggested_c2 = 8 + math.ceil(n_kf * 0.5 + n_kn * 0.3)
    suggested_c1 = 3 + max(5, suggested_c2 - 8)
    lines.append(f"建议完整性检查项数量: ~{suggested_c1}（3 项固定必需 + {suggested_c1 - 3} 项论文特定）")
    lines.append(f"建议正确性检查项数量: ~{suggested_c2}")
    lines.append(f"（公式: 8 + ceil({n_kf} key_figures × 0.5 + {n_kn} key_numbers × 0.3)）\n")

    lines.append(f"### key_numbers（{len(key_numbers)} 条——每条必须出现在至少一个正确性检查项中）：\n")
    for i, kn in enumerate(key_numbers, 1):
        condition = kn.get("condition") or kn.get("paper_anchor") or ""
        cond_str = f'（锚点: "{condition}"）' if condition else ""
        lines.append(f"- KN{i}: \"{kn['claim']}\"{cond_str}")
    lines.append("")

    lines.append(f"### traps（{len(traps)} 条——每条必须有专门的正确性检查项）：\n")
    for i, t in enumerate(traps, 1):
        lines.append(f"- TRAP{i}: [{t['kind']}]")
        lines.append(f"    正确表述: \"{t['correct_form']}\"")
        lines.append(f"    应避免的表述: \"{t['claim_to_avoid']}\"")
    lines.append("")

    if confused_terms:
        lines.append(f"### 带 common_confusion 的 key_terms（{len(confused_terms)} 条——每条必须有正确性检查项）：\n")
        for i, kt in enumerate(confused_terms, 1):
            lines.append(f"- KT{i}: \"{kt['term']}\" 易混淆为=\"{kt['common_confusion']}\"")
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
