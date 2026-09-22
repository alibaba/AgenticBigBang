# Expanded RL and second repair

`rre_expansion_manifest.csv` contains only the 2503 selected Expanded RL records
(A/B/C: 566/502/1435), representing 2497 unique tasks. It does not enumerate the
full candidate pool or excluded candidates. Raw and valid pass rates are separate
fields. `n_observed`, `n_valid`, `n_pass`, and `infra_failure_rows` record their
associated counts; the file does not specify the procedure for classifying validity.

`expanded_rl_record_id` identifies a source selection record; `anon_instance_id`
identifies its task using the same TRN namespace as the other manifests. Repeated
task records are retained rather than deduplicated.

`rre_repair_round2_sampling_manifest.csv` joins to that record ID and includes
all 2503 records, including zero-quota records.
`planned_trajectory_count` records the sampling quota.
`actual_sampled_trajectory_count` equals the quota, based on the authors'
confirmation that sampling was executed exactly as specified.
`evidence_type` is `author_confirmed_executed_quota`; this is not an
independent audit of trajectory contents. `available_reward1_row_count` counts
successful training rows, not necessarily unique trajectories.

Positive quota record counts are 549/487/1371; quota sums are 1392/1245/3840.
These are record-level counts and must not be described as unique task counts.
Eligibility, pass-rate bucket, and oversampling requirements are preserved.
This second-round file is separate from the existing first-round repair manifest.
No execution trajectories, original task
IDs, internal tables, partitions, or source paths are included.
