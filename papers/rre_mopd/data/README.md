# Training manifests and evaluation data

Start with the [manifest file guide](manifests/README.md) for the complete file
inventory, row counts, identifier relationships, and evaluation-table joins.
The [curve data guide](../results/curves/README.md) describes the pooled
category-dynamics data and plotting command.
Public benchmark data and construction notes are under [evaluation](evaluation).
The anonymous-data description below applies to the training manifests;
evaluation files retain public benchmark identifiers and task content.

This directory contains anonymous training membership tables and public
evaluation-task metadata. Training task content and execution trajectories
are not included.

## Initial expert RL

`manifests/initial_rl_training_records.csv` contains one row for each
materialized Initial-RL training record. `manifests/initial_rl_unique_instances.csv`
contains one row per unique underlying instance. The distinction is necessary
because the tables contain 2,769 Initial-RL training records but 2,768 distinct
tasks: one category-C instance occurs twice in the source records.

Training identifiers use `TRN-` for tasks and `REC-` for source records,
followed by 16 uppercase hexadecimal characters. Shared tasks and records
retain the same identifiers across the included manifests.

The Initial/pooled/balanced manifest columns disclose membership, category,
training phase, and record multiplicity. They do not disclose task text, repository identifiers,
patches, solutions, execution trajectories, or internal storage paths.

## Pooled joint RL

`manifests/pooled_training_records.csv` is the complete anonymous 6,723-record
pooled training manifest. It is the exact union of the 2,769 records represented
in `initial_rl_training_records.csv` and the 3,954 records represented in
`pooled_rest_training_records.csv`. Shared source records retain the same
anonymous record and instance IDs across manifests.

`manifests/pooled_unique_instances.csv` collapses repeated source records to
6,722 unique instances. `routing_group=U` denotes the 3,954-record remainder
outside the A/B/C Initial-RL pools; it is an anonymous routing-group label, not
the source dataset's own category field.

## Stratified balanced RL

`manifests/balanced_rl_training_records.csv` contains the 1,548 balanced
training instances: 516 each from A, B, and C. Every row is an exact subset of
the Initial-RL record mapping and therefore reuses the corresponding anonymous
record and instance IDs. No second ID namespace is introduced for the balanced
run.

## Validation

Run:

```bash
python3 scripts/validate_initial_rl_manifests.py
python3 scripts/validate_training_manifests.py
```

The checks verify the manifest counts, identifier format and uniqueness,
record-to-instance consistency, the documented duplicate, and a small set of
common identifier-leak patterns. It does not reproduce model training.

## Evaluation data

`manifests/evaluation_tasks.csv` lists 918 tasks across two benchmarks.
`manifests/evaluation_runs.csv` contains 60 runs: each model has three rounds
within its benchmark. The 33,264 outcomes are in
`../results/per_instance/evaluation_outcomes.csv`.
Training-task mastery is a separate table in
`../results/per_instance/training_instance_mastery.csv`; its `phase` and
`n_attempts` fields are not benchmark run labels.
