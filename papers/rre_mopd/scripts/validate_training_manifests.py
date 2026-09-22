#!/usr/bin/env python3
"""Validate Initial-RL, pooled-RL, and balanced-RL public manifests."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
INSTANCE_ID = re.compile(r"^TRN-[0-9A-F]{16}$")
RECORD_ID = re.compile(r"^REC-[0-9A-F]{16}$")
FORBIDDEN = ("__", "/Users/", "/mnt/", "gitlab", "@")


def load(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_ids(rows: list[dict[str, str]]) -> None:
    require(all(INSTANCE_ID.fullmatch(row["anon_instance_id"]) for row in rows), "Malformed instance ID")
    if rows and "anon_record_id" in rows[0]:
        require(all(RECORD_ID.fullmatch(row["anon_record_id"]) for row in rows), "Malformed record ID")
        require(len(rows) == len({row["anon_record_id"] for row in rows}), "Duplicate record ID")


def main() -> None:
    initial = load("initial_rl_training_records.csv")
    rest = load("pooled_rest_training_records.csv")
    pooled = load("pooled_training_records.csv")
    pooled_unique = load("pooled_unique_instances.csv")
    balanced = load("balanced_rl_training_records.csv")
    for rows in (initial, rest, pooled, pooled_unique, balanced):
        validate_ids(rows)

    require(len(initial) == 2769, "Initial-RL record count differs")
    require(len(rest) == 3954, "Rest record count differs")
    require(len(pooled) == 6723, "Pooled record count differs")
    require(len(pooled_unique) == 6722, "Pooled unique-instance count differs")
    require(len(balanced) == 1548, "Balanced record count differs")

    initial_record_ids = {row["anon_record_id"] for row in initial}
    rest_record_ids = {row["anon_record_id"] for row in rest}
    pooled_record_ids = {row["anon_record_id"] for row in pooled}
    balanced_record_ids = {row["anon_record_id"] for row in balanced}
    require(not (initial_record_ids & rest_record_ids), "Initial/rest record overlap")
    require(pooled_record_ids == initial_record_ids | rest_record_ids, "Pooled union differs")
    require(balanced_record_ids <= initial_record_ids, "Balanced records are not an Initial-RL subset")

    initial_instance_ids = {row["anon_instance_id"] for row in initial}
    rest_instance_ids = {row["anon_instance_id"] for row in rest}
    require(not (initial_instance_ids & rest_instance_ids), "Initial/rest instance overlap")
    require(
        {row["anon_instance_id"] for row in pooled_unique} == initial_instance_ids | rest_instance_ids,
        "Pooled unique-instance union differs",
    )
    require(len({row["anon_instance_id"] for row in balanced}) == 1548, "Balanced instances are not unique")

    require(Counter(row["routing_group"] for row in balanced) == Counter({"A": 516, "B": 516, "C": 516}), "Balanced category counts differ")
    require(Counter(row["source_subset"] for row in pooled) == Counter({"initial_rl": 2769, "rest_3954": 3954}), "Pooled subset counts differ")
    require(all(row["routing_group"] == "U" for row in rest), "Rest routing group differs")

    multiplicity = Counter(row["anon_instance_id"] for row in pooled)
    declared = {row["anon_instance_id"]: int(row["pooled_record_count"]) for row in pooled_unique}
    require(dict(multiplicity) == declared, "Pooled multiplicity declaration differs")
    require(Counter(multiplicity.values()) == Counter({1: 6721, 2: 1}), "Unexpected pooled duplicates")

    for path in MANIFESTS.glob("*.csv"):
        # Public evaluation IDs and run IDs are not anonymous training IDs.
        with path.open(newline="", encoding="utf-8") as handle:
            columns = next(csv.reader(handle))
        if "anon_instance_id" not in columns:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for fragment in FORBIDDEN:
            require(fragment.lower() not in text, f"Potential private identifier in {path.name}: {fragment}")

    print("PASS: Initial-RL + rest_3954 = 6,723 pooled records; balanced is a 1,548-record Initial-RL subset.")


if __name__ == "__main__":
    main()
