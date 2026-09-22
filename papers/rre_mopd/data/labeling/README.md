# Benchmark annotations

`benchmark_labels.jsonl` contains 1,531 existing structured annotations:

| corpus_id | Tasks |
| --- | ---: |
| swe_bench_verified_500 | 500 |
| swe_bench_pro | 731 |
| swe_bench_multilingual | 300 |

No DeepSWE records are included. This is a field-restricted export of existing
annotations, not a new labeling run. Label values, empty strings and L2 lists
are preserved without corrections or imputation. Public benchmark task IDs and
repository names remain available for joins. Training-instance anonymous IDs
are unrelated to these public benchmark IDs.

## Schema and scope

Each line contains `corpus_id`, `instance_id`, `repo`, and `labels`.
The key is `(corpus_id, instance_id)`; `repo` groups repositories across corpora.
`labels` contains the original `code_language`, `task_type_l1`, `domain_l1`,
`task_spec_type`, `dependency_context`, `task_type_l2`, `domain_l2`, `scope`,
`cognitive_complexity`, and `time_estimate`. L2 fields are lists; the other
label fields are strings. Their definitions are in `../taxonomy/` and the
shared SWE Labeler implementation.

This export omits issue/patch/test content, hints, timestamps, free-text
rationales and raw model responses. It contains neither private deployment
configuration. The annotation model was qwen3.7-max for all labeling, as
confirmed by the authors and recorded in ../../configs/labeling.yaml. It is sufficient
for the descriptive label distributions and structural audit, but not for
replaying the original annotation generation or assessing semantic accuracy.

## Reproduction

From the package root, with Python 3 and PyYAML installed:

```bash
python3 scripts/reproduce_labeling_audit.py
```

Outputs:

- `results/aggregate/labeling_structural_audit.csv`: inventory sizes,
  unspecified L2 outputs, repository consistency, empty Domain-L1 outputs,
  illegal concrete L1/L2 assignments and evaluation-category join counts.
- `results/aggregate/labeling_benchmark_profiles.csv`: label counts for each
  corpus, with both total-task and nonempty-output denominators explicit.

The structural audit uses all 1,531 records: Task-L2 unspecified is 70/1,531
(4.6%), Domain-L2 unspecified is 35/1,531 (2.3%), and 58/64 repositories have
one distinct nonempty Domain-L1 (90.6%). Six repositories have multiple
nonempty Domain-L1 labels; one task has an empty Domain-L1. Empty outputs are
not silently converted to `unspecified`. Concrete L2 labels are checked against
their own L1 definitions; `unspecified` is excluded from that concrete check.

Pro contains one empty annotation. For the manuscript's Pro profile,
345/730 gives 47.3% bug-fix and 432/730 gives 59.2% cross-module, whereas
243/731 gives 33.2% devops_infra. Both denominators are exposed in the output
instead of silently treating these as a single uniform percentage convention.
Language counts exclude empty outputs and use the label `code_language`.

All 618 Pro-618 and 300 Multilingual task IDs join to this export. Their
A/B/C/UNASSIGNED categories exactly match `../manifests/evaluation_tasks.csv`
when applying `../taxonomy/routing.json`. The remaining 113 Pro tasks remain
in the annotation corpus, not in the Pro-618 evaluation population.
