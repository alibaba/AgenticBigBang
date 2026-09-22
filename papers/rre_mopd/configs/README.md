# Experiment parameter specifications

These YAML files describe training and benchmark evaluation parameters. They are not executable launcher
configurations: the package does not include a training backend or environment
implementation. Values specify configuration settings, not independently measured
runtime behavior. Unlisted defaults are unspecified, not assumed to be zero or false.

## Training files

| Files in `training/` | Scope |
| --- | --- |
| `pooled_rl.yaml`, `balanced_rl.yaml` | Joint-training baselines. |
| `initial_rl_A.yaml`, `initial_rl_B.yaml`, `initial_rl_C.yaml` | Initial category experts. |
| `expanded_rl_A.yaml`, `expanded_rl_B.yaml`, `expanded_rl_C.yaml` | Expanded category experts. |
| `repair1_sft_A.yaml`, `repair1_sft_B.yaml`, `repair1_sft_C.yaml` | First repair SFT. |
| `repair2_sft_A.yaml`, `repair2_sft_B.yaml`, `repair2_sft_C.yaml` | Second repair SFT. |
| `mopd.yaml` | Dense-27B student distillation with A/B/C teacher routing. |

Each file has a `config_id` and `data_manifest`, with manifest paths relative
to the package root. Category files use the matching category rows. SFT manifests
describe sampling counts, not trajectory contents suitable for direct training.

`parameters` holds algorithm, rollout, sampling, and length settings. Worker
sections hold model precision, optimization, generation, and execution settings.
The files keep explicit differences between categories and stages rather than
requiring custom YAML inheritance. Training limits (`max_steps`) are configuration
limits, not evaluated model identifiers or evidence that every limit was reached.

For MOPD, teacher coefficients are `opd_kl_coef=1.0` and `exopd_lambda=1.25`.
The model architecture is `dense_27b`; no MoE-specific settings are present.
`parallel_layout_status=not_specified` means this file does not prescribe a
student/teacher/reference parallel layout. Do not infer a global optimizer batch
from per-device batch and accumulation settings alone.

The environment fields inside RL/MOPD files describe training rollouts. They do
not establish the final benchmark evaluation configuration. Separate supplied
benchmark specifications are available in evaluation/pro618.yaml and
evaluation/multilingual.yaml. See evaluation/README.md for missing dependencies
and the Pro anti-hacking configuration.

The author-confirmed annotation model is recorded in labeling.yaml. Pro prompt
templates and textual tool specifications are in evaluation/prompts/pro_r2e.yaml.

RL, MOPD, and benchmark evaluation specifications use a maximum of 150
interaction actions per trajectory. SFT does not perform online agent
rollouts, so its optimizer-step budgets are not interaction limits and remain
unchanged.

All files omit service credentials, deployment addresses, storage locations,
tracking metadata, model artifact identifiers, and scheduler launch commands.
