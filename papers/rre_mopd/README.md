![RRE-MOPD: Category-Aware Expert Training for Software Engineering Agents](./assets/rre-mopd-banner.jpg?raw=true)

# RRE-MOPD research artifacts

**One to More, More to One: Category-Aware Iterative Expert Training for
Software Engineering Agents**

[![arXiv](https://img.shields.io/badge/arXiv-2609.23377-b31b1b.svg)](https://arxiv.org/abs/2609.23377)
[![Hugging Face — Logics-SWE-Qwen3.6-27B](https://img.shields.io/badge/Hugging%20Face-Logics--SWE--Qwen3.6--27B-FFD21E?logo=huggingface&logoColor=FFD21E)](https://huggingface.co/Logics-MLLM/Logics-SWE-Qwen3.6-27B)
[![Hugging Face — Logics-SWE-Env-2.5K](https://img.shields.io/badge/Hugging%20Face-Logics--SWE--Env--2.5K-FFD21E?logo=huggingface&logoColor=FFD21E)](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K)

RRE–MOPD is the SWE research work in [Agentic Bigbang](../../README.md). Read
the paper on [arXiv](https://arxiv.org/abs/2609.23377).
It develops category experts through Refresh–Repair–Expand, then integrates
their behaviors into a single student with multi-teacher on-policy distillation.
The integrated model, [Logics-SWE-Qwen3.6-27B](https://huggingface.co/Logics-MLLM/Logics-SWE-Qwen3.6-27B),
is available on Hugging Face under Apache-2.0.
See the [project overview and main results](../../README.md#swe-research-rre-mopd)
and the [model card](MODEL_CARD.md) for the research summary and model usage.
This page focuses on the artifact package and local reproduction.

## Open dataset and execution environments

[Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K)
releases 2,553 software-engineering instances together with references to their
matching container environments. Each row uses `instance_id` as its stable task
identifier, `docker_image` as the released image reference, and `image_info` to
record the repository path, evaluator-script path, and runtime user inside that
image.

Download the dataset with the Hugging Face CLI:

```bash
pip install -U huggingface_hub
hf download Logics-MLLM/Logics-SWE-Env-2.5K \
  --repo-type dataset \
  --local-dir ./Logics-SWE-Env-2.5K
```

Inspect one instance without starting a container:

```bash
DATA=$(find ./Logics-SWE-Env-2.5K -type f -name '*.jsonl' -print -quit)
INSTANCE=openhpi__poseidon-566

python3 instance_environment/run_instance_image.py \
  --dataset "$DATA" \
  --instance-id "$INSTANCE" \
  --mode inspect
```

See [instance environment usage](instance_environment/README.md) for the image
contents, candidate/baseline/gold execution order, manual Docker workflow,
pass/fail semantics, and leakage-controlled evaluation protocol. The accompanying
[`run_instance_image.py`](instance_environment/run_instance_image.py) helper can
open an interactive shell or evaluate a candidate patch against the image's test
harness.

This package contains anonymous training manifests, benchmark task metadata,
per-task results, aggregate scores, and category-dynamics curve data.
The shared labeling implementation is available in [SWE Labeler](../../swe_labeler/).

## Contents

| Directory | Contents |
| --- | --- |
| [configs](configs/README.md) | Descriptive training and benchmark-evaluation parameter specifications. |
| [data/manifests](data/manifests/README.md) | Training membership lists and evaluation task/run metadata, with a file-by-file guide. |
| [data/evaluation/pro618](data/evaluation/pro618/README.md) | 731-task population, 618-task subset, category mapping, and reconstruction instructions. |
| [data/schemas](data/schemas/) | Field definitions and manifest schemas. |
| [results/per_instance](results/per_instance/) | Training mastery and benchmark outcomes. |
| [results/aggregate](results/aggregate/) | Derived round/category and model/category scores. |
| [results/curves](results/curves/README.md) | Pooled category dynamics, MOPD training metrics, and RRE training scores. |
| [results/figures](results/figures/README.md) | All 10 full-manuscript figure assets, their hashes, and reproduced plots. |
| [data/taxonomy](data/taxonomy/README.md) | Frozen definitions for the taxonomy figures. |
| [data/labeling](data/labeling/README.md) | 1,531 existing benchmark annotations and structural-audit reproduction. |
| [scripts](scripts/) | Manifest checks, evaluation aggregation, and plotting. |

Benchmark metadata covers 918 tasks and 60 runs, with three rounds per model
within each benchmark. Training mastery and curve replicates are separate tables;
see their field descriptions rather than treating them as additional benchmark runs.
Training task content and execution trajectories are not included.

## Run locally

From this directory, using Python 3.9 or newer:

```bash
python3 scripts/validate_initial_rl_manifests.py
python3 scripts/validate_training_manifests.py
python3 scripts/validate_package.py
python3 scripts/aggregate_evaluation_results.py
python3 scripts/reproduce_statistics.py
```

These commands use the Python standard library. Plotting additionally requires
`numpy` and `matplotlib`:

```bash
python3 scripts/plot_category_seesaw.py
python3 scripts/plot_mopd_training.py
python3 scripts/plot_rre_training.py
python3 scripts/plot_category_gains.py
python3 scripts/plot_pooled_balanced.py
```

The two taxonomy plotting scripts additionally require `pyyaml`; see the
[figure index](results/figures/README.md).

To verify the benchmark annotations and regenerate their descriptive statistics
(requires `pyyaml`): `python3 scripts/reproduce_labeling_audit.py`.

Aggregation regenerates files in `results/aggregate`; plotting validates its
input points and writes PDF and PNG outputs to `results/figures`.
All paths used by these scripts are relative to this package, so no private
workspace or credentials are needed.

See [statistical reproduction](scripts/STATISTICS.md) for record weighting,
paired bootstrap details, and the displayed-range curve summary.
