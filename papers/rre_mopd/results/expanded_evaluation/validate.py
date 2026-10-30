"""Validate the expanded score tables and task-level snapshots with stdlib."""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIGURE_DATA = ROOT.parent / "figures/expanded-eval/aggregate_results.json"
BENCHMARKS = {
    "SWE-bench Pro V2": "swe_bench_pro_v2",
    "Pro V2 Hard-51": "swe_bench_pro_v2_hard51",
    "SWE-bench Multilingual": "swe_bench_multilingual",
    "SWE-bench Pro": "swe_bench_pro",
    "LiveCodeBench v6": "livecodebench_v6",
}


def read(name):
    with (ROOT / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    figure = json.loads(FIGURE_DATA.read_text(encoding="utf-8"))
    expected_rounds = {}
    expected_means = {}
    for benchmark in figure["benchmarks"]:
        bid = BENCHMARKS[benchmark["name"]]
        total = benchmark["tasks"]
        for model, passes in zip(figure["model_order"], benchmark["passes"]):
            assert len(passes) == 3
            expected_means[bid, model] = (sum(passes), total)
            for entry, count in enumerate(passes, 1):
                expected_rounds[bid, model, entry] = (count, total)

    rounds = read("benchmark_round_scores.csv")
    assert len(rounds) == len(expected_rounds) == 60
    seen = set()
    for row in rounds:
        key = row["benchmark_id"], row["model"], int(row["score_entry"])
        assert key not in seen
        seen.add(key)
        passed, total = int(row["passed"]), int(row["tasks"])
        assert (passed, total) == expected_rounds[key]
        assert abs(float(row["score_pct"]) - 100 * passed / total) < 1e-6
        if row["result_type"]:
            assert key == ("livecodebench_v6", "Logics-SWE-Qwen3.6-27B", 2)
            assert row["result_type"] == "selective_rerun_merge"
    assert seen == set(expected_rounds)

    means = read("benchmark_model_scores.csv")
    assert len(means) == len(expected_means) == 20
    seen = set()
    for row in means:
        key = row["benchmark_id"], row["model"]
        assert key not in seen
        seen.add(key)
        passed, total = int(row["passed_sum"]), int(row["tasks_per_entry"])
        assert (passed, total) == expected_means[key] and int(row["n_entries"]) == 3
        assert abs(float(row["mean_score_pct"]) - 100 * passed / (3 * total)) < 1e-6
    assert seen == set(expected_means)

    manifests = read("instance_run_manifest.csv")
    run_map = {}
    for row in manifests:
        key = row["benchmark_id"], row["model"], int(row["score_entry"])
        assert key not in run_map and key in expected_rounds
        run_map[key] = row
    expected_task_runs = {
        (benchmark, model, entry)
        for benchmark in ("swe_bench_pro_v2", "swe_bench_multilingual")
        for model in figure["model_order"]
        for entry in (1, 2, 3)
    }
    expected_task_runs.remove(("swe_bench_multilingual", "Qwen3.6-35B-A3B", 2))
    assert set(run_map) == expected_task_runs

    tasks_by_run = defaultdict(dict)
    hard_sets = []
    for filename, benchmark in (
        ("pro_v2_instance_results.csv", "swe_bench_pro_v2"),
        ("multilingual_instance_results.csv", "swe_bench_multilingual"),
    ):
        for row in read(filename):
            key = benchmark, row["model"], int(row["score_entry"])
            assert key in run_map
            iid = row["instance_id"]
            assert iid and iid not in tasks_by_run[key]
            assert row["result_status"] in ("scored", "unscored")
            if row["result_status"] == "scored":
                assert row["score"] in ("0", "1")
            else:
                assert row["score"] == ""
            if benchmark == "swe_bench_pro_v2":
                assert row["hard51"] in ("true", "false")
            tasks_by_run[key][iid] = row

    assert set(tasks_by_run) == set(run_map)
    task_sets = defaultdict(list)
    for key, tasks in tasks_by_run.items():
        manifest = run_map[key]
        scored = sum(t["result_status"] == "scored" for t in tasks.values())
        passed = sum(t["score"] == "1" for t in tasks.values())
        assert len(tasks) == int(manifest["tasks"])
        assert scored == int(manifest["scored"]) and passed == int(manifest["passed"])
        assert (passed, len(tasks)) == expected_rounds[key]
        task_sets[key[0]].append(set(tasks))
        if key[0] == "swe_bench_pro_v2":
            hard = {i for i, t in tasks.items() if t["hard51"] == "true"}
            hard_sets.append(hard)
            hard_pass = sum(tasks[i]["score"] == "1" for i in hard)
            assert (hard_pass, len(hard)) == expected_rounds[
                "swe_bench_pro_v2_hard51", key[1], key[2]
            ]
    for sets in task_sets.values():
        assert all(s == sets[0] for s in sets)
    assert all(s == hard_sets[0] for s in hard_sets)
    assert len(task_sets["swe_bench_pro_v2"][0]) == 642
    assert len(task_sets["swe_bench_multilingual"][0]) == 300
    assert len(hard_sets[0]) == 51
    print(
        f"Validated {len(rounds)} score entries, {len(means)} model means, "
        f"{len(run_map)} task-level runs and "
        f"{sum(map(len, tasks_by_run.values()))} task results."
    )


if __name__ == "__main__":
    main()
