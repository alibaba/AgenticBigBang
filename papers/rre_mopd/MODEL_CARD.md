---
base_model:
- Qwen/Qwen3.6-27B
datasets:
- Logics-MLLM/Logics-SWE-Env-2.5K
license: apache-2.0
library_name: transformers
pipeline_tag: text-generation
tags:
- code
- software-engineering
- on-policy-distillation
- reinforcement-learning
- agentic-post-training
---

# Logics-SWE-Qwen3.6-27B

[![arXiv](https://img.shields.io/badge/arXiv-2609.23377-b31b1b.svg)](https://arxiv.org/abs/2609.23377)
[![GitHub](https://img.shields.io/badge/GitHub-AgenticBigBang-181717.svg?logo=github)](https://github.com/alibaba/AgenticBigBang)

Official model release for
[_One to More, More to One: Category-Aware Iterative Expert Training for Software Engineering Agents_](https://arxiv.org/abs/2609.23377).

[📄 Paper](https://arxiv.org/abs/2609.23377) ·
[🤗 Dataset: Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K) ·
[💻 GitHub: AgenticBigBang](https://github.com/alibaba/AgenticBigBang)

## 📰 News

- **[2026.10.30]** Submitted the expanded paper as arXiv v2 and added results on Pro V2, Hard-51, Multilingual, SWE-bench Pro, and LiveCodeBench v6. We also report a 35B-A3B student trained with the same three 27B category experts.
- **[2026.09.20]** Released the [RRE–MOPD paper](https://arxiv.org/abs/2609.23377) on arXiv.
- **[2026.09.18]** Released **Logics-SWE-Qwen3.6-27B** under the Apache-2.0 license.

## 🔎 Overview

**Logics-SWE-Qwen3.6-27B** is a 27B-parameter model developed for repository-level
software engineering agents. Starting from the Qwen3.6-27B model used in our
study, it combines category-aware expert development with multi-teacher
on-policy distillation into a single deployment policy.

Repository-level tasks require agents to navigate code, edit files, execute
commands, inspect feedback, and iteratively repair their solutions. Our work
starts from the **category see-saw**: aggregate progress during joint RL can
conceal opposing changes across task categories. Category splitting alone
does not guarantee stronger experts. We therefore develop the experts through
RRE before integrating their learned behaviors into one model.

### Stage 1: Refresh–Repair–Expand expert development

SWE Labeler organizes training tasks into three repository-domain categories:

- **A:** service, data, and security.
- **B:** user-facing applications.
- **C:** systems, tooling, and runtimes.

All experts start from the same base model. **Refresh–Repair–Expand (RRE)**
alternates executable-reward RL with supervised replay of each expert's own
verified successful trajectories. Mastery refreshes track how task success
rates change; repair consolidates successful behavior, and expansion revisits
additional tasks to identify the next training frontier. Agentic-miniRL
provides the shared long-horizon RL recipe.

### Stage 2: Single-policy integration with MOPD

The student starts from the common base and generates its own trajectories.
Each training task is routed to its corresponding category expert for
token-level supervision. Reference-anchored extrapolation augments imitation,
using a positive teacher–reference gap gate. The student receives no direct
environment-reward term during this pure distillation stage.

Neither expert development nor integration uses an
external model to provide solution trajectories or action targets.

Here, integration means **on-policy distillation**, not arithmetic averaging
of expert weights. Inference uses one model; category labels and separate
expert models are not required for deployment.

**Intended use:** research on repository-level issue resolution, coding agents,
long-horizon post-training, expert development, and policy distillation.

## 📊 Experimental Results

### Expanded evaluation

Logics-SWE-Qwen3.6-27B improves on Qwen3.6-27B across four
software-engineering and coding evaluations. Scores are three-round means (%);
gains are in percentage points.

![Logics-SWE benchmark results](results/figures/expanded-eval/model_benchmark_comparison.png)

| Evaluation | Tasks per round | Qwen3.6-27B | Logics-SWE-Qwen3.6-27B | Gain |
| --- | ---: | ---: | ---: | ---: |
| SWE-bench Pro V2 | 642 | 81.62 | **86.19** | **+4.57** |
| Pro V2 Hard-51 | 51 | 37.25 | **42.48** | **+5.23** |
| SWE-bench Multilingual | 300 | 67.89 | **71.78** | **+3.89** |
| SWE-bench Pro | 731 | 52.94 | **56.41** | **+3.47** |
| LiveCodeBench v6 | 175 | 82.48 | **84.57** | **+2.10** |

The figure also shows a Qwen3.6-35B-A3B student distilled using the same
three 27B category experts. Qwen baseline scores are from our own evaluations
under the same settings as Logics-SWE.

### Pro-618 in the original paper

The original paper reports **58.04 ± 0.20%** for Logics-SWE-Qwen3.6-27B and
**52.64 ± 0.28%** for Qwen3.6-27B on Pro-618, a 618-task subset of SWE-bench
Pro. Values are the mean ± population standard deviation over three
evaluation rounds.


## 🚀 Quickstart

### Transformers: text-generation smoke test

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "Logics-MLLM/Logics-SWE-Qwen3.6-27B"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    dtype=torch.bfloat16,
    device_map="auto",
)
model.eval()

messages = [{
    "role": "user",
    "content": "A parser crashes on an empty input file. Describe how you would "
               "investigate the cause, implement a fix, and test for regressions.",
}]
inputs = tokenizer.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
).to(model.device)

with torch.inference_mode():
    output = model.generate(
        **inputs,
        max_new_tokens=1024,
        do_sample=True,
        temperature=1.0,
        top_p=0.95,
        top_k=20,
    )
completion = output[0, inputs["input_ids"].shape[-1]:]
print(tokenizer.decode(completion, skip_special_tokens=True))
```

The example follows the Transformers
[chat-template interface](https://huggingface.co/docs/transformers/main/en/chat_templating).
Its short generation budget is for demonstration only. Repository-level agent
use additionally requires the matching system prompt, tool schema, action
parser, sandbox, and verifier. Model-generated commands should not be executed
automatically outside an isolated, permission-controlled environment.

## 📦 Training Data and Release Scope

The public [Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K)
release provides 2,553 software-engineering task instances and their matching
environment-image references. It is a curated subset of the training tasks
used in the paper; it does not contain the complete training corpus or agent
trajectories.

The [AgenticBigBang GitHub repository](https://github.com/alibaba/AgenticBigBang)
additionally provides the label
taxonomy, SWE Labeler code, anonymous training manifests, benchmark outcomes,
aggregate results, and training and evaluation configuration specifications.

## 📚 Citation

If you use this model, please cite:

```bibtex
@misc{zhao2026onetomoremoretoone,
  title         = {One to More, More to One: Category-Aware Iterative Expert Training for Software Engineering Agents},
  author        = {Jie Zhao and Ziyu Jiang and Suhang Zheng and Minghui Shan and Xiaoxiao Xu and Lin Qu},
  year          = {2026},
  eprint        = {2609.23377},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE},
  url           = {https://arxiv.org/abs/2609.23377}
}
```

## 🙏 Acknowledgements

We thank the Qwen, ROLL, R2E-Gym, SWE-agent, SWE-bench, SWE-bench Pro, and
SWE-bench Multilingual contributors, and the research communities behind
MiniRL, MOPD, and ExOPD.

## License

The model weights are released under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
