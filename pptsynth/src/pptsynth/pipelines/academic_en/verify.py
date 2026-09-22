"""Multi-aspect post-hoc validator for an out_root of synthesized cases.

Content-driven item count ranges (C1: 9-18, C2: 8-20)
to accommodate paper-adaptive item counts. Validates the 11-axis audit
schema. Read-only; does not modify any case files.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema  # type: ignore


_FORBIDDEN_META_INSTRUCTIONS = [
    "PPTSynth",
    "pptsynth",
    "PPTSYNTH",
    "self-check",
    "self check",
    "as required to satisfy",
]

_REQUIRED_INSTR_ANCHORS = [
    "Strict Constraints for the Slides",
    "## 1. Content Requirements",
    "## 2. Content Constraints",
    "## 3. Visual & Design",
    "## 4. Text Quality",
    "## 5. Technical Fidelity Requirements",
    "## 6. Presentation Tone and Audience",
    "# **Output Expected**",
]


@dataclass
class CaseReport:
    case_slug: str
    ok: bool
    issues: list[str] = field(default_factory=list)


def _check_paper_card(case_dir: Path, schemas_dir: Path, issues: list[str]) -> dict | None:
    p = case_dir / "_paper_card.json"
    if not p.exists():
        issues.append("missing _paper_card.json")
        return None
    try:
        card = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"_paper_card.json invalid JSON: {e}")
        return None
    schema = json.loads((schemas_dir / "paper_card.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(card))
    for e in errors[:5]:
        path = "/".join(map(str, e.path)) or "<root>"
        issues.append(f"paper_card schema: {path}: {e.message}")
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
    for term in _FORBIDDEN_META_INSTRUCTIONS:
        if term in text:
            issues.append(f"instructions.md contains forbidden meta term: {term!r}")
    if "Design Constraint:" not in text or text.count("Design Constraint:") < 3:
        issues.append(
            f"instructions.md has too few Design Constraint: lines ({text.count('Design Constraint:')})"
        )
    for marker in ["Paper Title:", "Author Team:", "Affiliation:", "Conference:"]:
        if marker not in text:
            issues.append(f"title slide missing field: {marker!r}")
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
        issues.append(f"judge_prompt.json keys must be exactly the two checklist arrays; got {sorted(data.keys())}")
    c1 = data.get("material_dependent_checklist_1") or []
    c2 = data.get("material_dependent_checklist_2") or []
    if not (9 <= len(c1) <= 18):
        issues.append(f"completeness count out of [9,18]: {len(c1)}")
    if not (8 <= len(c2) <= 20):
        issues.append(f"correctness count out of [8,20]: {len(c2)}")
    for i, item in enumerate(c1, 1):
        if not isinstance(item, str) or "?" not in item or "**" not in item:
            issues.append(f"completeness[{i}] malformed")
    for i, item in enumerate(c2, 1):
        if not isinstance(item, str) or "?" not in item or "**" not in item:
            issues.append(f"correctness[{i}] malformed")
        elif "If **no**" not in item:
            issues.append(f"correctness[{i}] missing 'If **no**' instruction")
    return data


def _check_audit(case_dir: Path, schemas_dir: Path, issues: list[str]) -> dict | None:
    p = case_dir / "_audit_report.json"
    if not p.exists():
        # Audit is optional for the post-hoc verifier; warn but don't fail.
        issues.append("note: _audit_report.json absent (was Stage 4 run?)")
        return None
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        issues.append(f"_audit_report.json invalid JSON: {e}")
        return None
    schema = json.loads((schemas_dir / "audit_report.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(report))
    for e in errors[:5]:
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
        # Verify-refine is optional (conditional trigger); absence is not an issue.
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
        errors = list(validator.iter_errors(report))
        for e in errors[:5]:
            path = "/".join(map(str, e.path)) or "<root>"
            issues.append(f"verify_refine_report schema: {path}: {e.message}")
    if not report.get("verified"):
        issues.append("verify_refine_report.verified is false")
    return report


def _cross_consistency(card: dict | None, instructions_text: str | None, judge: dict | None, issues: list[str]) -> None:
    if not (card and instructions_text and judge):
        return
    title = card.get("title") or ""
    if title and title not in instructions_text:
        # Some papers have very long titles that get reformatted; still flag.
        issues.append("paper title not found verbatim in instructions.md (may indicate paraphrase)")
    # Check that at least 3 figure ids from key_figures are referenced in instructions
    fig_ids = {f.get("id") for f in (card.get("key_figures") or []) if f.get("id")}
    hits = sum(1 for fid in fig_ids if fid and fid in instructions_text)
    if fig_ids and hits < min(3, len(fig_ids)):
        issues.append(
            f"only {hits}/{len(fig_ids)} key_figures referenced in instructions.md (need >=3)"
        )
    # At least 2 key_numbers mentioned in correctness checklist (approximate
    # by substring match on the value).
    c2_blob = "\n".join(judge.get("material_dependent_checklist_2") or [])
    matched = 0
    for n in card.get("key_numbers") or []:
        claim = n.get("claim") or ""
        # Try the first numeric token as a rough anchor
        import re

        for tok in re.findall(r"[0-9]+(?:\.[0-9]+)?%?", claim):
            if tok in c2_blob:
                matched += 1
                break
    if matched < 2:
        issues.append(
            f"only {matched} key_numbers anchors found in correctness checklist (want >=2)"
        )


def verify_case(case_dir: Path, schemas_dir: Path) -> CaseReport:
    issues: list[str] = []
    if not (case_dir / "material.pdf").exists():
        issues.append("missing material.pdf")
    card = _check_paper_card(case_dir, schemas_dir, issues)
    instructions_text = _check_instructions(case_dir, issues)
    judge = _check_judge(case_dir, issues)
    _check_audit(case_dir, schemas_dir, issues)
    _check_verify_refine(case_dir, schemas_dir, issues)
    _cross_consistency(card, instructions_text, judge, issues)

    blocking = [i for i in issues if not i.startswith("note:")]
    return CaseReport(case_slug=case_dir.name, ok=not blocking, issues=issues)


def verify_all(out_root: Path) -> list[CaseReport]:
    schemas_dir = Path(__file__).resolve().parent / "schemas"
    academia = out_root / "academia"
    if not academia.exists():
        return []
    return [verify_case(d, schemas_dir) for d in sorted(academia.iterdir()) if d.is_dir()]


def main() -> int:
    ap = argparse.ArgumentParser(prog="pptsynth_synth_rubricsrefineAB5.verify")
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--strict", action="store_true", help="non-zero exit if any case fails")
    args = ap.parse_args()
    if not args.out_root.exists():
        print(f"out-root not found: {args.out_root}", file=sys.stderr)
        return 2
    reports = verify_all(args.out_root)
    n_ok = sum(1 for r in reports if r.ok)
    print(f"verified {len(reports)} cases: {n_ok} ok, {len(reports) - n_ok} fail")
    for r in reports:
        if not r.ok or any(not i.startswith("note:") for i in r.issues):
            print(f"\n  [{r.case_slug}]")
            for issue in r.issues:
                print(f"    - {issue}")
    return 1 if args.strict and n_ok < len(reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
