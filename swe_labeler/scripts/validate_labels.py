#!/usr/bin/env python3
"""
SWE Labeler - Label Validation Script

Validates labeled output for:
- L1→L2 consistency (L2 must be valid child of L1)
- Label distribution (no L2 with 0 instances)
- Unspecified rate
- Missing/invalid fields

Usage:
    python scripts/validate_labels.py --output-dir ./output
    python scripts/validate_labels.py --file ./output/swe_bench_verified_500_labeled.jsonl
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import load_yaml

DEFINITION_DIR = Path(__file__).parent.parent / "definition"


def load_valid_l2_map(dimension: str) -> dict[str, list[str]]:
    if dimension == "task_type":
        defs = load_yaml(str(DEFINITION_DIR / "task_type_l2.yaml"))
    elif dimension == "domain":
        defs = load_yaml(str(DEFINITION_DIR / "domain_l2.yaml"))
    else:
        return {}

    result = {}
    for l1_key, l1_data in defs.items():
        if not isinstance(l1_data, dict):
            continue
        l2_list = l1_data.get("l2")
        if l2_list is None:
            result[l1_key] = []
        elif isinstance(l2_list, list):
            result[l1_key] = [item["name"] for item in l2_list if "name" in item]
        else:
            result[l1_key] = []
    return result


def validate_file(filepath: str, task_type_map: dict, domain_map: dict) -> dict:
    stats = {
        "total": 0,
        "valid": 0,
        "errors": [],
        "task_type_l1": Counter(),
        "task_type_l2": Counter(),
        "domain_l1": Counter(),
        "domain_l2": Counter(),
        "scope": Counter(),
        "cognitive_complexity": Counter(),
        "time_estimate": Counter(),
        "code_language": Counter(),
        "l2_unspecified_task_type": 0,
        "l2_unspecified_domain": 0,
        "no_labels": 0,
    }

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                stats["errors"].append(f"Line {line_num}: invalid JSON")
                continue

            stats["total"] += 1
            labels = obj.get("labels")
            if not labels or not isinstance(labels, dict):
                stats["no_labels"] += 1
                continue

            task_l1 = labels.get("task_type_l1", "")
            task_l2 = labels.get("task_type_l2", [])
            domain_l1 = labels.get("domain_l1", "")
            domain_l2 = labels.get("domain_l2", [])

            # normalize L2 to list (backward compat with old string format)
            if isinstance(task_l2, str):
                task_l2 = [task_l2] if task_l2 else ["unspecified"]
            if isinstance(domain_l2, str):
                domain_l2 = [domain_l2] if domain_l2 else ["unspecified"]

            stats["task_type_l1"][task_l1] += 1
            for t in task_l2:
                stats["task_type_l2"][t] += 1
            stats["domain_l1"][domain_l1] += 1
            for d in domain_l2:
                stats["domain_l2"][d] += 1
            stats["scope"][labels.get("scope", "")] += 1
            stats["cognitive_complexity"][labels.get("cognitive_complexity", "")] += 1
            stats["time_estimate"][labels.get("time_estimate", "")] += 1
            stats["code_language"][labels.get("code_language", "")] += 1

            if task_l2 == ["unspecified"] or not task_l2:
                stats["l2_unspecified_task_type"] += 1
            if domain_l2 == ["unspecified"] or not domain_l2:
                stats["l2_unspecified_domain"] += 1

            valid_task_l2s = task_type_map.get(task_l1, [])
            if valid_task_l2s:
                for t in task_l2:
                    if t and t != "unspecified" and t not in valid_task_l2s:
                        stats["errors"].append(
                            f"Line {line_num} ({obj.get('instance_id', '?')}): "
                            f"task_type_l2='{t}' is not valid under L1='{task_l1}'"
                        )

            valid_domain_l2s = domain_map.get(domain_l1, [])
            if valid_domain_l2s:
                for d in domain_l2:
                    if d and d != "unspecified" and d not in valid_domain_l2s:
                        stats["errors"].append(
                            f"Line {line_num} ({obj.get('instance_id', '?')}): "
                            f"domain_l2='{d}' is not valid under L1='{domain_l1}'"
                        )

            stats["valid"] += 1

    return stats


def print_report(filepath: str, stats: dict):
    print(f"\n{'='*70}")
    print(f"Validation Report: {os.path.basename(filepath)}")
    print(f"{'='*70}")
    print(f"Total instances:       {stats['total']}")
    print(f"Valid (with labels):   {stats['valid']}")
    print(f"Missing labels:        {stats['no_labels']}")
    print(f"L1→L2 errors:          {len(stats['errors'])}")
    print(f"L2 unspecified (task): {stats['l2_unspecified_task_type']} ({stats['l2_unspecified_task_type']/max(stats['total'],1)*100:.1f}%)")
    print(f"L2 unspecified (domain): {stats['l2_unspecified_domain']} ({stats['l2_unspecified_domain']/max(stats['total'],1)*100:.1f}%)")

    print(f"\n--- Task Type L1 Distribution ---")
    for label, count in stats["task_type_l1"].most_common(15):
        print(f"  {label:<25} {count:>5} ({count/max(stats['total'],1)*100:.1f}%)")

    print(f"\n--- Domain L1 Distribution ---")
    for label, count in stats["domain_l1"].most_common(15):
        print(f"  {label:<25} {count:>5} ({count/max(stats['total'],1)*100:.1f}%)")

    print(f"\n--- Code Language Distribution ---")
    for label, count in stats["code_language"].most_common(10):
        print(f"  {label:<15} {count:>5} ({count/max(stats['total'],1)*100:.1f}%)")

    print(f"\n--- Scope Distribution ---")
    for label, count in stats["scope"].most_common():
        print(f"  {label:<25} {count:>5}")

    print(f"\n--- Cognitive Complexity Distribution ---")
    for label, count in stats["cognitive_complexity"].most_common():
        print(f"  {label:<25} {count:>5}")

    print(f"\n--- Time Estimate Distribution ---")
    for label, count in stats["time_estimate"].most_common():
        print(f"  {label:<25} {count:>5}")

    if stats["errors"]:
        print(f"\n--- Errors (first 20) ---")
        for err in stats["errors"][:20]:
            print(f"  {err}")

    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate SWE labeler output")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory containing labeled JSONL files")
    parser.add_argument("--file", type=str, default=None, help="Single JSONL file to validate")
    args = parser.parse_args()

    task_type_map = load_valid_l2_map("task_type")
    domain_map = load_valid_l2_map("domain")

    files = []
    if args.file:
        files = [args.file]
    elif args.output_dir:
        files = sorted(Path(args.output_dir).glob("*_labeled.jsonl"))
    else:
        default_dir = Path(__file__).parent.parent / "output"
        files = sorted(default_dir.glob("*_labeled.jsonl"))

    if not files:
        print("No labeled files found. Run the labeling pipeline first.")
        return

    for filepath in files:
        filepath = str(filepath)
        stats = validate_file(filepath, task_type_map, domain_map)
        print_report(filepath, stats)


if __name__ == "__main__":
    main()
