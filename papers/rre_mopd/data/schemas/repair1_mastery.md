# First repair sampling and training mastery

This document describes the two CSV files included in this package. Paths below
are relative to the package root. The repair manifest describes sampling counts;
the mastery result table describes per-task success rates. They join through
`anon_instance_id` but have different row keys and purposes.

## First repair manifest

`data/manifests/rre_repair_sampling_manifest.csv` contains one row per unique
Initial-RL task, including tasks not sampled for repair. It covers repair round 1
only, not the second repair round. `anon_instance_id` uses the same TRN identifiers
as the other training manifests. Category counts are A=601, B=516, C=1651.

- `repair_round`: 1.
- `selected_for_sft`: whether at least one trajectory was actually sampled.
- `sampled_trajectory_count`: actual SFT rows attributed to the task.
- `planned_trajectory_count`: planned strict first-round sampling quota.
- `available_success_key_count`: count of distinct successful RL trajectory keys;
  not a count of benchmark successes.

Actual sampled task counts are 571/501/1498 and trajectory counts are
1623/1481/4384 for A/B/C, respectively. These are counts, not released trajectories.

## Training mastery results

`results/per_instance/training_instance_mastery.csv` has one row for each
task and phase (`base`, `initial_rl`, `repair_sft`), totaling 8304 rows.
The key is `(anon_instance_id, phase)`.

- `n_successes`: success count recorded for this task and phase.
- `n_attempts`: denominator recorded for this task and phase's success rate.
  It is not a training-record multiplicity or a trajectory sampling quota.
- `success_rate`: `n_successes / n_attempts`, on the 0–1 scale.
- `infra_failure_count`: recorded infrastructure-failure count for Initial RL
  and Repair SFT. Base entries in this table are blank;
  blank must not be interpreted as zero. This field is diagnostic and does not
  subtract attempts from the denominator.

For paper statistics, join these rates to
`data/manifests/initial_rl_training_records.csv` on `anon_instance_id`.
Give each training record equal weight: A=601, B=516, C=1652 (2769 total).
The repeated C task contributes twice, using the same observed rate; this
does not add independent rollout attempts. The underlying task-level files
remain at 2768 tasks and are not duplicated. Do not pool attempt counts,
which would introduce a different weighting.

`python3 scripts/reproduce_statistics.py` regenerates the record-weighted
means, gain/loss counts and repair cohorts in `results/aggregate/`.
Repair exposure is a membership indicator in that analysis: actual SFT
trajectory totals must still be summed from the original repair manifest,
not from a multiplicity-expanded join.
No original training task identifiers, execution trajectories, internal partition
names, or filesystem paths are included in the exported CSV files.
