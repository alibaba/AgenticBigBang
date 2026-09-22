# SWE Labeler

SWE Labeler assigns hierarchical labels to software-engineering tasks and agent
trajectories. It predicts task type and application domain at two levels (L1 and
L2), plus scope, cognitive complexity, and estimated effort.

This public snapshot contains the taxonomy, prompts, generic labeling code,
synthetic fixtures, and tests. It intentionally excludes training/evaluation
datasets, real interaction trajectories, model checkpoints, API credentials,
logs, caches, and organization-specific data adapters.

## Labeling modes

### Task-instance labeling

Use `scripts/run_label.py` for SWE-style records containing fields such as
`instance_id`, `repo`, `problem_statement`, `patch`, and `test_patch`. The
pipeline performs L1 classification followed by L2 refinement and the three
orthogonal dimensions.

### Trajectory labeling

Trajectory JSONL records may provide a `messages` list directly or through
`json_content`.

- `scripts/run_trajectory_label.py` performs L2-only labeling and requires
  valid existing L1 labels.
- `scripts/run_trajectory_full_label.py` performs complete L1+L2 labeling.
  `--l1-mode preserve` keeps a complete valid L1 result and generates missing
  or invalid L1 fields; `--l1-mode relabel` recomputes L1 for every record.

The full pipeline derives stable source hashes for safe resume behavior. It
stops before calling the LLM if an existing output cannot be matched safely.

## Installation

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy a sample configuration to a gitignored local file, then set your own
OpenAI-compatible endpoint, model name, and API key environment variable.

```bash
cp config/labeler_config.yaml config/local_labeler_config.yaml
export LLM_API_KEY="replace-with-your-key"
```

Never commit a real token to a YAML file.

## Quick start

Run task-instance labeling on the synthetic example:

```bash
python scripts/run_label.py \
  --config config/local_labeler_config.yaml \
  --skip-enrich \
  --limit 1
```

Run complete trajectory labeling:

```bash
python scripts/run_trajectory_full_label.py \
  --config config/labeler_config_trajectory_full.yaml \
  --input examples/trajectories/raw_trajectory.jsonl \
  --l1-mode preserve \
  --limit 1
```

Run L2-only trajectory labeling on records that already contain L1 labels:

```bash
python scripts/run_trajectory_label.py \
  --config config/labeler_config_trajectory.yaml \
  --input examples/trajectories/l1_labeled_trajectory.jsonl \
  --limit 1
```

Replace the example endpoint and model before executing a live request.

## Input schemas

A generic task-instance record looks like:

```json
{"instance_id":"example-1","repo":"example/project","problem_statement":"Handle an empty configuration file.","patch":"diff --git a/parser.py b/parser.py\n...","test_patch":""}
```

A generic trajectory record looks like:

```json
{"trajectory_id":"trajectory-1","messages":[{"role":"user","content":"Fix the parser and add a regression test."},{"role":"assistant","content":"I will inspect the parser."}]}
```

For L2-only mode, add a `labels` object containing `code_language`,
`task_type_l1`, `domain_l1`, `task_spec_type`, and `dependency_context`.

## Outputs and privacy boundary

Outputs are JSONL and may retain the original task text, patches, trajectory
content, model/scaffold metadata, rationales, and raw model responses. The
configured LLM endpoint receives prompt content derived from the input. Review
the input, endpoint, and generated output before sharing any artifact.

See [DATA_POLICY.md](DATA_POLICY.md) and [SECURITY.md](SECURITY.md) before using
the code with non-public data.

## Validation and tests

```bash
pytest -q
python scripts/validate_labels.py --file path/to/labeled_output.jsonl
```

## License

SWE Labeler is licensed under the [Apache License, Version 2.0](LICENSE)
(SPDX: `Apache-2.0`). This license covers the original SWE Labeler code and
original accompanying materials in this directory; third-party material
retains its applicable terms and attributions. It does not license datasets,
model weights, or other projects in the parent repository.

See [LICENSE_STATUS.md](LICENSE_STATUS.md) for the license scope and
[DATA_POLICY.md](DATA_POLICY.md) for data handling and release boundaries.
