# Expanded evaluation data

This directory contains the scores shown in the [benchmark comparison](../figures/expanded-eval/model_benchmark_comparison.png), together with task-level results for SWE-bench Pro V2 and SWE-bench Multilingual. The two students are [Logics-SWE-Qwen3.6-27B](https://huggingface.co/Logics-MLLM/Logics-SWE-Qwen3.6-27B) and [Logics-SWE-Qwen3.6-35B-A3B](https://huggingface.co/Logics-MLLM/Logics-SWE-Qwen3.6-35B-A3B); the corresponding baselines are [Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) and [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B). Qwen baseline scores are from our own evaluations.

| File | Contents |
| --- | --- |
| [benchmark_round_scores.csv](benchmark_round_scores.csv) | Pass counts, task counts, and percentages for three score entries per benchmark and model. |
| [benchmark_model_scores.csv](benchmark_model_scores.csv) | Three-entry means computed from the unrounded counts. |
| [pro_v2_instance_results.csv](pro_v2_instance_results.csv) | All 642 Pro V2 task results for each model and score entry; includes Hard-51 membership. |
| [multilingual_instance_results.csv](multilingual_instance_results.csv) | Multilingual task results for both Logics-SWE models and the available baseline score entries. |
| [instance_run_manifest.csv](instance_run_manifest.csv) | Task-level coverage, pass counts, snapshot dates, and selection methods. |
| [validate.py](validate.py) | Checks the tables against each other and the figure's source data. |

## Benchmarks

| `benchmark_id` | Evaluation | Tasks per entry | Setup |
| --- | --- | ---: | --- |
| `swe_bench_pro_v2` | [SWE-bench Pro V2](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro) | 642 | mini-SWE-agent 2.4.6 and patch replay |
| `swe_bench_pro_v2_hard51` | Pro V2 Hard-51 | 51 | Subset of the corresponding Pro V2 run |
| `swe_bench_multilingual` | [SWE-bench Multilingual](https://huggingface.co/datasets/SWE-bench/SWE-bench_Multilingual) | 300 | SWE-agent |
| `swe_bench_pro` | SWE-bench Pro | 731 | SWE-agent |
| `livecodebench_v6` | LiveCodeBench v6 | 175 | Code generation and judge |

The Pro V2 instance IDs match the default and Hard subsets at dataset revision [`2d52cb3`](https://huggingface.co/datasets/ScaleAI/SWE-bench_Pro/tree/2d52cb3df914a3fcf80c7f66738b3a88ae37fc50); the Multilingual instance IDs match the test set at revision [`846e647`](https://huggingface.co/datasets/SWE-bench/SWE-bench_Multilingual/tree/846e647b9f33c0b51b739d005d13d85493c9af09).

## Reading the tables

`score_entry` identifies a selected score entry within a model and benchmark. The order follows the figure's source data; it is not a chronological run number or a random seed. Hard-51 entries share the same `score_entry` as their Pro V2 parent. Percentages use the listed full task count as the denominator, and means are calculated from pass counts before rounding. The 149-pass LiveCodeBench entry for Logics-SWE-Qwen3.6-27B incorporates a selective rerun merge, identified by `result_type`.

In task-level files, `score` is 1 or 0 when a result was scored and is empty when no score was available. `result_status` records that distinction. The manifest records the snapshot date and selection method: `confirmed_selection` denotes a confirmed 27B selection, `matched_source` denotes a matched source, and `source_table_inferred` identifies a source-table mapping. Task results for the second Qwen3.6-35B-A3B Multilingual entry are not included because its per-task source is not uniquely identified; its aggregate score is present in the benchmark tables.

The original-paper [evaluation manifests](../../data/manifests/README.md), [task outcomes](../per_instance/evaluation_outcomes.csv), and [aggregate tables](../aggregate/) remain available for reproducing the earlier experiments. They are separate from this expanded evaluation.

## Validate

From this directory:

```bash
python3 validate.py
```

The validator checks score counts and means against the figure's [source JSON](../figures/expanded-eval/aggregate_results.json), verifies task-level keys and score coverage, and recomputes Pro V2, Hard-51, and available Multilingual counts.
