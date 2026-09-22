# Pro-618 evaluation data

## Included files

- `swebench_pro_731.jsonl`: 731 distinct task records.
- `pro618_instances.jsonl`: 618 distinct task records, all present in the 731-task file.
- `verified_task_mapping.csv`: 618 task IDs with task indices and Pro-A/B/C labels.
- [pro618_selection_manifest.csv](../../manifests/pro618_selection_manifest.csv): inclusion flags, exclusion reasons, and index correspondence for all 731 tasks.

Join by `instance_id`, not by row position. The `idx` values differ between the
two JSONL files. For the 618 common tasks, all other task fields are identical.

## Membership and exclusion labels

The manifest contains 618 rows with `included_in_pro618=true` and 113 with
`included_in_pro618=false`. The excluded rows contain these reason labels:

| `exclusion_reason` | Meaning | Rows |
| --- | --- | ---: |
| `specification_determinacy_defect` | Specification/determinacy defect | 83 |
| `underspecified_grading_choice` | Underspecified grading choice | 26 |
| `reference_patch_grader_failure` | Reference-patch grader failure | 3 |
| `prompt_test_mismatch` | Prompt/test mismatch | 1 |
| Total | | 113 |

Each excluded task has one reason label, giving 731 - 113 = 618 retained tasks.
Excluded rows have the recorded status `verified_against_source_manifest`;
retained rows have `not_applicable` and a blank reason. `exclusion_note` is blank.
These are the annotations present in the CSV; this package does not contain
per-task audit evidence or code to independently verify the defect classifications.

## Reconstruct the included subset

1. Read the 731-task JSONL and key its records by `instance_id`.
2. Read manifest rows with `included_in_pro618=true`.
3. Retrieve those task records, order them by numeric `pro618_idx`, and set
   each record's `idx` to `pro618_idx`.
4. Join `verified_task_mapping.csv` by `instance_id` for category labels.

The manifest's `full_idx` corresponds to the 731-task file. `pro618_idx` and the
mapping's `task_idx` correspond to the 618-task file.

## Task fields and categories

The task JSONL files contain task fields including repository identity, base
commit, problem statement, patches, test information, and `dockerhub_tag`.
They do not contain a `docker_image` field. `dockerhub_tag` is a tag string,
not a complete image address.

The JSONL `category` field is `swebench-pro`; A/B/C labels are in the mapping:

| Mapping label | Unified category | Tasks |
| --- | --- | ---: |
| Pro-A | A | 221 |
| Pro-B | B | 201 |
| Pro-C | C | 196 |
| Total | | 618 |

The same assignments appear in
[evaluation_tasks.csv](../../manifests/evaluation_tasks.csv) under
`benchmark_id=pro618`. Use that unified task table for score aggregation.
This directory contains task data and categories. Evaluation runs and task-level
outcomes are documented in [evaluation_results.md](../../schemas/evaluation_results.md).
