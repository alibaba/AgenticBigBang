---
license: apache-2.0
pipeline_tag: text-generation
tags:
  - code
  - software-engineering
  - reinforcement-learning
  - on-policy-distillation
  - agentic-post-training
# Add the exact base_model Hub ID when confirmed.
---

# Logics-SWE-Qwen3.6-27B

> Model card for Logics-SWE-Qwen3.6-27B. The technical report is in preparation.

## 📰 News

- **[2026.09.18]** Released **Logics-SWE-Qwen3.6-27B** under the Apache-2.0 license.
- The technical report is in preparation. A link will be added when available.

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

Values are mean task resolution (%) ± population standard deviation across
three evaluation rounds, with one candidate patch per task per round.

| Model | Pro-618 | SWE-bench Multilingual |
| --- | ---: | ---: |
| Base | 52.64 ± 0.28 | 56.22 ± 0.68 |
| Pooled RL | 55.50 ± 0.46 | 55.56 ± 0.83 |
| Balanced RL | 55.34 ± 0.92 | 57.00 ± 1.19 |
| **Logics-SWE-Qwen3.6-27B** | **58.04 ± 0.20** | **59.00 ± 0.47** |

Compared with the base model, Logics-SWE-Qwen3.6-27B improves mean task
resolution from **52.64% to 58.04%** on Pro-618 (**+5.40 percentage points**)
and from **56.22% to 59.00%** on SWE-bench Multilingual
(**+2.78 percentage points**).

| Final model category | Pro-618 | SWE-bench Multilingual |
| --- | ---: | ---: |
| A | 58.07 ± 1.13 | 51.39 ± 1.13 |
| B | 59.37 ± 1.02 | 64.00 ± 3.27 |
| C | 56.63 ± 1.10 | 61.74 ± 0.27 |

### Evaluation scope

- **Pro-618** retains 618 of 731 SWE-bench Pro tasks using documented public
  audit findings. Its A/B/C counts are 221/201/196. These are subset results,
  not full SWE-bench Pro scores.
- **SWE-bench Multilingual** includes all 300 tasks. A/B/C contain 72/25/176
  tasks; 27 unrouted tasks remain in the Full denominator.
- Scores measure the complete agent setup, not standalone text generation.
  Pro uses the study's R2E-Gym-based setup; Multilingual uses a SWE-agent
  setup. Absolute scores across the two scaffolds are not directly comparable.
- Unsuccessful or missing evaluations remain in the fixed task denominator.


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

Alongside the released model weights, we plan to make the following resources
publicly available:

- A curated subset of instance-level training data, subject to approval.
- The label taxonomy, annotation guidelines, and SWE Labeler code.
- Anonymous training manifests, benchmark outcomes, aggregate results, and
  training and evaluation configuration specifications.

## 📚 Citation

The technical report is in preparation. Citation information will be added upon release.

## 🙏 Acknowledgements

We thank the Qwen, ROLL, R2E-Gym, SWE-agent, SWE-bench, SWE-bench Pro, and
SWE-bench Multilingual contributors, and the research communities behind
MiniRL, MOPD, and ExOPD.

## License

The model weights are released under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
