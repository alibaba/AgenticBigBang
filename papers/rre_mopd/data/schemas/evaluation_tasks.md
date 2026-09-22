# Evaluation tasks

`data/manifests/evaluation_tasks.csv` is the unified task/category table for
evaluation aggregation. Its primary key is `(benchmark_id, instance_id)`.

- `benchmark_id`: `pro618` or `swebench_multilingual`.
- `instance_id`: original public benchmark task ID.
- `category`: `A`, `B`, `C`, or `UNASSIGNED`.

Pro-618 has 618 tasks (A=221, B=201, C=196). Multilingual has 300 tasks
(A=72, B=25, C=176, UNASSIGNED=27). The 27 UNASSIGNED tasks remain in
the Multilingual Full denominator of 300; do not discard or force-route them.

Obtain benchmark_id from evaluation_runs when joining evaluation_outcomes.
This file records membership and categories, not task prompts or outcomes.
Pro-618 assignments are normalized from the supplied verified mapping's
Pro-A/Pro-B/Pro-C labels. That mapping is retained as the source index crosswalk;
use this unified file for category aggregation. The separate 731-instance
selection manifest documents benchmark construction, not evaluation outcomes.
