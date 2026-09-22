"""Post-hoc validator for broad_domain_synth out_root.

Validates cases under out_root/<primary>/<secondary>/<slug>/.
Checks: doc_card schema, instructions.md structure, judge_prompt.json,
audit_report schema, verify_refine_report schema, cross-consistency.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema  # type: ignore

from ._anti_leakage import PRE_DISCLOSURE_PATTERNS, FORBIDDEN_META_TERMS

_REQUIRED_INSTR_ANCHORS = [
    "幻灯片的严格约束",
    "## 1. 内容要求",
    "## 2. 内容约束",
    "## 3. 视觉与设计",
    "## 4. 文本质量",
    "## 5. 技术忠实性要求",
    "## 6. 演示风格与听众",
    "# **预期输出**",
]


@dataclass
class CaseReport:
    case_slug: str
    primary: str
    secondary: str
    ok: bool
    issues: list[str] = field(default_factory=list)


def _check_doc_card(case_dir: Path, schemas_dir: Path, issues: list[str]) -> dict | None:
    # Accept either _doc_card.json or _paper_card.json
    p = case_dir / "_doc_card.json"
    if not p.exists():
        p = case_dir / "_paper_card.json"
    if not p.exists():
        issues.append("missing _doc_card.json")
        return None
    try:
        card = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"_doc_card.json invalid JSON: {e}")
        return None
    schema_path = schemas_dir / "doc_card.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for e in list(validator.iter_errors(card))[:5]:
            path = "/".join(map(str, e.path)) or "<root>"
            issues.append(f"doc_card schema: {path}: {e.message}")
    return card


def _check_instructions(case_dir: Path, issues: list[str]) -> str | None:
    p = case_dir / "generation_task" / "instructions.md"
    if not p.exists():
        issues.append("missing instructions.md")
        return None
    text = p.read_text(encoding="utf-8")
    if len(text) < 1500:
        issues.append(f"instructions.md too short ({len(text)} bytes)")
    for ph in _REQUIRED_INSTR_ANCHORS:
        if ph not in text:
            issues.append(f"instructions.md missing anchor: {ph!r}")
    for term in FORBIDDEN_META_TERMS:
        if term in text:
            issues.append(f"instructions.md contains forbidden meta term: {term!r}")
    dc_count = text.count("设计约束:") + text.count("设计约束：")
    if dc_count < 2:
        issues.append(f"instructions.md has too few 设计约束 lines ({dc_count})")
    return text


def _check_judge(case_dir: Path, issues: list[str]) -> dict | None:
    p = case_dir / "generation_task" / "judge_prompt.json"
    if not p.exists():
        issues.append("missing judge_prompt.json")
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"judge_prompt.json invalid JSON: {e}")
        return None
    if set(data.keys()) != {"material_dependent_checklist_1", "material_dependent_checklist_2"}:
        issues.append(f"judge_prompt.json keys mismatch; got {sorted(data.keys())}")
    c1 = data.get("material_dependent_checklist_1") or []
    c2 = data.get("material_dependent_checklist_2") or []
    if not (9 <= len(c1) <= 35):
        issues.append(f"completeness count out of [9,35]: {len(c1)}")
    if not (8 <= len(c2) <= 35):
        issues.append(f"correctness count out of [8,35]: {len(c2)}")
    for i, item in enumerate(c1, 1):
        if not isinstance(item, str) or ("?" not in item and "？" not in item) or "**" not in item:
            issues.append(f"completeness[{i}] malformed")
    for i, item in enumerate(c2, 1):
        if not isinstance(item, str) or ("?" not in item and "？" not in item) or "**" not in item:
            issues.append(f"correctness[{i}] malformed")
        elif "如果**否**" not in item and "If **no**" not in item:
            issues.append(f"correctness[{i}] missing '如果**否**' instruction")
    return data


def _check_audit(case_dir: Path, schemas_dir: Path, issues: list[str]) -> dict | None:
    p = case_dir / "_audit_report.json"
    if not p.exists():
        issues.append("note: _audit_report.json absent (was Stage 4 run?)")
        return None
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"_audit_report.json invalid JSON: {e}")
        return None
    schema = json.loads((schemas_dir / "audit_report.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for e in list(validator.iter_errors(report))[:5]:
        path = "/".join(map(str, e.path)) or "<root>"
        issues.append(f"audit_report schema: {path}: {e.message}")
    if not report.get("pass"):
        scores = report.get("scores") or {}
        failing = sorted(k for k, v in scores.items() if isinstance(v, int) and v < 4)
        issues.append(f"audit not passing; failing axes: {failing}")
    return report


def _check_verify_refine(case_dir: Path, schemas_dir: Path, issues: list[str]) -> dict | None:
    p = case_dir / "_verify_refine_report.json"
    if not p.exists():
        return None
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"_verify_refine_report.json invalid JSON: {e}")
        return None
    schema_path = schemas_dir / "verify_refine_report.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for e in list(validator.iter_errors(report))[:5]:
            path = "/".join(map(str, e.path)) or "<root>"
            issues.append(f"verify_refine_report schema: {path}: {e.message}")
    if not report.get("verified"):
        issues.append("verify_refine_report.verified is false")
    return report


def _cross_consistency(card: dict | None, instructions_text: str | None, judge: dict | None, issues: list[str]) -> None:
    if not (card and instructions_text and judge):
        return
    title = card.get("title") or ""
    if title and len(title) < 100 and title not in instructions_text:
        issues.append("doc title not found verbatim in instructions.md")
    fig_ids = {f.get("id") for f in (card.get("key_figures") or []) if f.get("id")}
    hits = sum(1 for fid in fig_ids if fid and fid in instructions_text)
    if fig_ids and hits < min(2, len(fig_ids)):
        issues.append(f"only {hits}/{len(fig_ids)} key_figures referenced in instructions.md")
    import re
    c2_blob = "\n".join(judge.get("material_dependent_checklist_2") or [])
    matched = 0
    for n in card.get("key_numbers") or []:
        claim = n.get("claim") or ""
        for tok in re.findall(r"[0-9]+(?:\.[0-9]+)?%?", claim):
            if tok in c2_blob:
                matched += 1
                break
    if matched < 2:
        issues.append(f"only {matched} key_numbers anchors in correctness checklist (want >=2)")


def verify_case(case_dir: Path, schemas_dir: Path, primary: str = "", secondary: str = "") -> CaseReport:
    issues: list[str] = []
    if not (case_dir / "material.pdf").exists():
        issues.append("missing material.pdf")
    card = _check_doc_card(case_dir, schemas_dir, issues)
    instructions_text = _check_instructions(case_dir, issues)
    judge = _check_judge(case_dir, issues)
    _check_audit(case_dir, schemas_dir, issues)
    _check_verify_refine(case_dir, schemas_dir, issues)
    _cross_consistency(card, instructions_text, judge, issues)
    blocking = [i for i in issues if not i.startswith("note:")]
    return CaseReport(
        case_slug=case_dir.name,
        primary=primary,
        secondary=secondary,
        ok=not blocking,
        issues=issues,
    )


def verify_all(out_root: Path) -> list[CaseReport]:
    schemas_dir = Path(__file__).resolve().parent / "schemas"
    reports: list[CaseReport] = []
    # Walk out_root/<primary>/<secondary>/<case>/
    for primary_dir in sorted(out_root.iterdir()):
        if not primary_dir.is_dir() or primary_dir.name.startswith("_"):
            continue
        for secondary_dir in sorted(primary_dir.iterdir()):
            if not secondary_dir.is_dir() or secondary_dir.name.startswith("_"):
                continue
            for case_dir in sorted(secondary_dir.iterdir()):
                if case_dir.is_dir() and not case_dir.name.startswith("_"):
                    reports.append(
                        verify_case(case_dir, schemas_dir, primary_dir.name, secondary_dir.name)
                    )
    return reports


def main() -> int:
    ap = argparse.ArgumentParser(prog="broad_domain_synth.verify")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    if not args.out_root.exists():
        print(f"out-root not found: {args.out_root}", file=sys.stderr)
        return 2
    reports = verify_all(args.out_root)
    n_ok = sum(1 for r in reports if r.ok)
    print(f"verified {len(reports)} cases: {n_ok} ok, {len(reports) - n_ok} fail")
    for r in reports:
        if not r.ok:
            print(f"\n  [{r.primary}/{r.secondary}/{r.case_slug}]")
            for issue in r.issues:
                print(f"    - {issue}")
    return 1 if args.strict and n_ok < len(reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
