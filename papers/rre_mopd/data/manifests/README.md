# Manifest guide / 数据清单索引

This directory contains training membership lists and evaluation metadata, not
execution trajectories. Files are grouped below by purpose; their locations are
unchanged. Counts describe the current package snapshot.

## Where to start

- To identify training data: read the record manifest for the relevant stage.
- To reproduce benchmark scores: join `evaluation_tasks.csv` and
  `evaluation_runs.csv` to [evaluation_outcomes.csv](../../results/per_instance/evaluation_outcomes.csv).
- To compare training-task mastery before and after repair: use
  [training_instance_mastery.csv](../../results/per_instance/training_instance_mastery.csv).
- To understand the 731-to-618 benchmark construction: read
  [the Pro-618 construction explanation](../evaluation/pro618/README.md).

## Training data files

| File | Rows | Meaning of one row / purpose |
| --- | ---: | --- |
| [initial_rl_training_records.csv](initial_rl_training_records.csv) | 2,769 | One Initial-RL source record; A/B/C have 601/516/1,652 records. |
| [initial_rl_unique_instances.csv](initial_rl_unique_instances.csv) | 2,768 | One distinct Initial-RL task, with its source-record multiplicity; derived from the record list. |
| [pooled_training_records.csv](pooled_training_records.csv) | 6,723 | One pooled-RL training record; union of Initial RL and the remainder below. |
| [pooled_rest_training_records.csv](pooled_rest_training_records.csv) | 3,954 | One record in the pooled remainder outside Initial RL; a component of pooled, not another experiment. |
| [pooled_unique_instances.csv](pooled_unique_instances.csv) | 6,722 | One distinct pooled task, with multiplicity; derived from pooled records. |
| [balanced_rl_training_records.csv](balanced_rl_training_records.csv) | 1,548 | One selected balanced-RL record; 516 tasks in each category, all from Initial RL. |
| [rre_repair_sampling_manifest.csv](rre_repair_sampling_manifest.csv) | 2,768 | One Initial-RL task and its first-repair sampling counts, including tasks with zero samples. |
| [rre_expansion_manifest.csv](rre_expansion_manifest.csv) | 2,503 | One selected Expanded-RL record; A/B/C have 566/502/1,435 records, representing 2,497 unique tasks. |
| [rre_repair_round2_sampling_manifest.csv](rre_repair_round2_sampling_manifest.csv) | 2,503 | One Expanded-RL record and its second-repair sampling quota, including zero-quota records. |
| [mopd_training_records.csv](mopd_training_records.csv) | 4,956 | One materialized MOPD training copy; 1,652 per category, covering 2,768 unique tasks. |

The unique-instance files are convenient deduplicated views, not additional
training datasets. Do not sum their row counts with the record-file counts.
Initial RL contains two records for one C task, hence 2,769 records versus 2,768
tasks; that distinction also explains pooled's 6,723 versus 6,722 counts.

First repair sampled 2,570 tasks and 7,488 trajectories (A/B/C:
1,623/1,481/4,384). Second repair has 2,407 positive-quota records and 6,477
trajectory slots (1,392/1,245/3,840). The authors confirmed that these quotas
were executed as recorded. `actual_sampled_trajectory_count` therefore equals
`planned_trajectory_count`, with `evidence_type=author_confirmed_executed_quota`.
This is an author-confirmed count, not an independent trajectory-level audit.

Expanded RL lists training records with `selected_for_expanded_rl=true`.
This file has no rows marked false.

## Evaluation metadata files

| File | Rows | Meaning of one row / purpose |
| --- | ---: | --- |
| [evaluation_tasks.csv](evaluation_tasks.csv) | 918 | One public benchmark task and category: 618 Pro-618 tasks and 300 Multilingual tasks. |
| [evaluation_runs.csv](evaluation_runs.csv) | 60 | One evaluation run: model, stage, benchmark, round, and coverage counts. |
| [pro618_selection_manifest.csv](pro618_selection_manifest.csv) | 731 | One task from the original Pro population, with inclusion flag and original/subset index correspondence. |

The 60 runs comprise 48 Pro-618 and 12 Multilingual evaluations. Their 33,264
task-level outcomes cover three rounds for each model within each benchmark.
There are 16 model entries for Pro-618 and four for Multilingual. These
task-level outcomes are stored under `results/per_instance`, not duplicated
here. Missing results are explicit rows with zero score and `result_status=missing`;
all benchmark denominators remain fixed. Multilingual's 27 `UNASSIGNED` tasks
remain in its Full denominator of 300.

The Pro-618 selection file records exact membership. The overall exclusion
rationale and 83/26/3/1 accounting are documented in the benchmark README;
all 113 excluded rows have a populated `exclusion_reason`. The other 618 rows
have blank exclusion reasons and `reason_status=not_applicable`.

## How identifiers connect the files

| Key | Meaning and joins |
| --- | --- |
| `anon_instance_id` (`TRN-*`) | Stable training-task identity across all stages and the mastery results. Repeated records share it. |
| `anon_record_id` (`REC-*`) | Initial/pooled/balanced source-record identity; distinguishes duplicate source records for the same task. |
| `source_record_id` | MOPD reference to an Initial-RL `anon_record_id`. |
| `mopd_record_id` (`MOPD-*`) | Unique materialized MOPD copy; `upsample_occurrence` counts copies of a source record. |
| `expanded_rl_record_id` (`ERL-*`) | Expanded-RL selection-record identity, shared by its second-repair row. |
| `(benchmark_id, instance_id)` | Public evaluation task identity; use both fields when joining task metadata. |
| `run_id` | Evaluation-run identity; joins the run list to outcomes. Outcome key: `(run_id, instance_id)`. |

`round` is a replicate label within a model and benchmark, not a random seed.
`config_id` links to the shared released parameter specification:
`pro618_eval` or `multilingual_eval`. It is not a runtime receipt.

Training `routing_group=U` marks the pooled remainder outside the Initial-RL
A/B/C pools; evaluation `category=UNASSIGNED` marks unassigned benchmark tasks.
They describe different populations and should not be conflated.

## Summary JSON files

These are generated audit summaries, not additional datasets:

- [initial_rl_manifest_summary.json](initial_rl_manifest_summary.json): counts,
  identifier scheme, duplicate multiplicity, and output hashes.
- [pooled_manifest_summary.json](pooled_manifest_summary.json): pooled counts,
  component relationship, and output hashes.
- [balanced_rl_manifest_summary.json](balanced_rl_manifest_summary.json):
  balanced counts, subset relationship, and output hashes.
- [mopd_manifest_summary.json](mopd_manifest_summary.json): category counts,
  upsampling multiplicity, and manifest hash.

## Detailed fields and checks

Field-level descriptions and JSON schemas are in [../schemas](../schemas):
[first repair/mastery](../schemas/repair1_mastery.md),
[Expanded RL/second repair](../schemas/rre_expansion_and_repair2.md),
[MOPD](../schemas/mopd_training_records.md),
[evaluation tasks](../schemas/evaluation_tasks.md), and
[evaluation results](../schemas/evaluation_results.md).

From the package root:

```bash
python3 scripts/validate_initial_rl_manifests.py
python3 scripts/validate_training_manifests.py
python3 scripts/aggregate_evaluation_results.py
```

The first two scripts check Initial/pooled/balanced manifests; they are not
validators for every training stage. The third checks all three evaluation
tables and regenerates round/category and model/category aggregates. Aggregate
outputs should be regenerated, not manually maintained as another source of truth.

Training identifiers are anonymous; their private mappings and HMAC key are
not distributed. Evaluation instance IDs remain the original public IDs.
