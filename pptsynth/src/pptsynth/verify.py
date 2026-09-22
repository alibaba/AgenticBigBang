"""Read-only structural verifier for unified PPTSynth output."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def verify_case(case_dir: Path) -> list[str]:
    issues: list[str] = []
    route = case_dir / "_routing.json"
    task = case_dir / "generation_task"
    rubric = task / "judge_prompt.json"
    instructions = task / "instructions.md"
    if not route.exists():
        issues.append("missing _routing.json")
    if not instructions.exists():
        issues.append("missing instructions.md")
    if not rubric.exists():
        issues.append("missing judge_prompt.json")
        return issues
    try:
        data = json.loads(rubric.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return issues + [f"invalid judge_prompt.json: {exc}"]
    for key in ("material_dependent_checklist_1", "material_dependent_checklist_2"):
        value = data.get(key)
        if not isinstance(value, list) or not value:
            issues.append(f"missing or empty {key}")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate PPTSynth output without model calls.")
    ap.add_argument("--out-root", type=Path, required=True)
    args = ap.parse_args()
    cases = sorted({p.parent.parent for p in args.out_root.rglob("generation_task/judge_prompt.json")})
    if not cases:
        print("no cases found", file=sys.stderr)
        return 2
    failed = 0
    for case in cases:
        issues = verify_case(case)
        print(f"{'FAIL' if issues else 'OK  '} {case}: {'; '.join(issues) if issues else ''}")
        failed += bool(issues)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
