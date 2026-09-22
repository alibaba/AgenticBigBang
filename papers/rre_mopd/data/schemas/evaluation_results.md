# Evaluation runs and outcomes

The three source tables are `data/manifests/evaluation_tasks.csv`,
`data/manifests/evaluation_runs.csv`, and
`results/per_instance/evaluation_outcomes.csv`.

## Runs

`run_id` is unique. `benchmark_id` links to the task manifest. `model_id`, `stage`,
and `expert_category` identify the reported policy. `config_id` references
`configs/evaluation/pro618.yaml` (`pro618_eval`) or `multilingual.yaml`
(`multilingual_eval`). This links shared parameter specifications, not
independently verified historical runtime receipts.

`round` is a one-based replicate label within a model and benchmark, not a
random seed. `included_in_paper` indicates whether a run contributes to the
reported aggregates. Counts record expected, observed, and missing tasks.

Every `(benchmark_id, model_id)` group contains exactly three runs, labeled
1, 2, and 3. There are 48 Pro-618 runs and 12 Multilingual runs. This round
field is unrelated to `n_attempts` in the separate training mastery table.

## Outcomes

The key is `(run_id, instance_id)`. Join to runs for the benchmark, then to tasks
by `(benchmark_id, instance_id)` for categories. `score` is the binary score used
for aggregation. `result_status=observed` means a scalar result was available,
not necessarily successful execution or task resolution. `missing` denotes an
absent source row and has score zero under the fixed-denominator protocol.

`failure_type` records recognizable infrastructure-failure labels or
`missing_result`; blank means no such type was exported, not proof of fault-free
execution. `termination_reason` retains short source stop/end labels when present.
No exception text or trajectory content is included. Existing observed scores
are preserved even when execution metadata indicates a failure.

Pro-618 denominators are Full=618, A=221, B=201, C=196. Multilingual denominators
are Full=300, A=72, B=25, C=176, UNASSIGNED=27. Missing tasks remain in each
denominator. Full scores are task-weighted, not an unweighted category mean.

Run `python3 scripts/aggregate_evaluation_results.py` from the bundle to validate
keys and coverage and regenerate `results/aggregate/evaluation_round_scores.csv`
and `evaluation_model_scores.csv`. Cross-round standard deviations use ddof=0.
Derived aggregate files are disposable outputs of the three source tables.
Routed expert category results can be assembled from the respective final experts;
they are not an independently executed fourth expert model.
