#!/usr/bin/env python3
"""Validate the public Initial-RL manifests without private source data."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "data" / "manifests"
RECORDS_PATH = MANIFEST_DIR / "initial_rl_training_records.csv"
INSTANCES_PATH = MANIFEST_DIR / "initial_rl_unique_instances.csv"
SUMMARY_PATH = MANIFEST_DIR / "initial_rl_manifest_summary.json"
INSTANCE_ID = re.compile(r"^TRN-[0-9A-F]{16}$")
RECORD_ID = re.compile(r"^REC-[0-9A-F]{16}$")
EXPECTED_RECORDS = {"A": 601, "B": 516, "C": 1652}
EXPECTED_UNIQUE = {"A": 601, "B": 516, "C": 1651}
FORBIDDEN_FRAGMENTS = ("__", "/Users/", "/mnt/", "gitlab", "@")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    records = load_csv(RECORDS_PATH)
    instances = load_csv(INSTANCES_PATH)
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    require(len(records) == 2769, f"Expected 2769 records, got {len(records)}")
    require(len(instances) == 2768, f"Expected 2768 unique instances, got {len(instances)}")

    record_ids = [row["anon_record_id"] for row in records]
    instance_ids = [row["anon_instance_id"] for row in instances]
    require(len(record_ids) == len(set(record_ids)), "Duplicate anon_record_id")
    require(len(instance_ids) == len(set(instance_ids)), "Duplicate anon_instance_id")
    require(all(RECORD_ID.fullmatch(value) for value in record_ids), "Malformed anon_record_id")
    require(all(INSTANCE_ID.fullmatch(value) for value in instance_ids), "Malformed anon_instance_id")

    known_instances = set(instance_ids)
    require(
        all(row["anon_instance_id"] in known_instances for row in records),
        "Record references an unknown anon_instance_id",
    )
    require(
        all(row["training_phase"] == "initial_expert_rl" for row in records),
        "Unexpected training_phase",
    )

    record_counts = Counter(row["category"] for row in records)
    unique_counts = Counter(row["category"] for row in instances)
    require(dict(record_counts) == EXPECTED_RECORDS, f"Record counts differ: {dict(record_counts)}")
    require(dict(unique_counts) == EXPECTED_UNIQUE, f"Unique counts differ: {dict(unique_counts)}")

    multiplicity = Counter(row["anon_instance_id"] for row in records)
    require(Counter(multiplicity.values()) == Counter({1: 2767, 2: 1}), "Unexpected record multiplicity")
    declared = {row["anon_instance_id"]: int(row["initial_rl_record_count"]) for row in instances}
    require(declared == dict(multiplicity), "Declared record multiplicity differs from record manifest")

    for path in (RECORDS_PATH, INSTANCES_PATH):
        text = path.read_text(encoding="utf-8")
        for fragment in FORBIDDEN_FRAGMENTS:
            require(fragment.lower() not in text.lower(), f"Potential identifier leak in {path.name}: {fragment}")

    require(summary["counts"]["training_records"] == 2769, "Summary record count differs")
    require(summary["counts"]["unique_instances"] == 2768, "Summary unique count differs")
    require(summary["id_scheme"]["secret_material_in_public_bundle"] is False, "Invalid key disclosure flag")
    print("PASS: 2,769 Initial-RL records map to 2,768 anonymous unique instances.")


if __name__ == "__main__":
    main()
