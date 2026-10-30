---
base_model:
- Qwen/Qwen3.6-35B-A3B
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

# Logics-SWE-Qwen3.6-35B-A3B

[![arXiv](https://img.shields.io/badge/arXiv-2609.23377-b31b1b.svg)](https://arxiv.org/abs/2609.23377)
[![GitHub](https://img.shields.io/badge/GitHub-AgenticBigBang-181717.svg?logo=github)](https://github.com/alibaba/AgenticBigBang)

**Logics-SWE-Qwen3.6-35B-A3B** is a software engineering model developed from
[Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) using
category-aware multi-teacher on-policy distillation (MOPD). It brings together
the capabilities of three software engineering experts in a single model for
repository-level coding agents.

[Paper](https://arxiv.org/abs/2609.23377) ·
[GitHub: AgenticBigBang](https://github.com/alibaba/AgenticBigBang) ·
[Logics-SWE-Qwen3.6-27B](https://huggingface.co/Logics-MLLM/Logics-SWE-Qwen3.6-27B) ·
[Dataset: Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K)

## 📰 News

- **[2026.10.30]** Introduced Logics-SWE-Qwen3.6-35B-A3B, trained with MOPD using the same three 27B category experts as Logics-SWE-Qwen3.6-27B.

## Highlights

- **One policy, three experts.** The model integrates three category experts
  into one student that can work across repository domains without selecting
  an expert at inference time.
- **Reuse of 27B teachers.** The same three final Qwen3.6-27B-based experts
  used for Logics-SWE-Qwen3.6-27B are reused to train the 35B-A3B student.
- **Improved SWE and coding results.** Compared with Qwen3.6-35B-A3B, the
  model improves by **3.69 points** on SWE-bench Pro V2, **3.00 points** on
  SWE-bench Multilingual, and **2.37 points** on SWE-bench Pro.

## How It Works

Repository-level software engineering tasks span different domains, from
services and data systems to user-facing applications and developer tools.
The RRE–MOPD approach develops complementary specialists and combines their
knowledge into a single agent model:

1. **Organize tasks.** SWE Labeler assigns tasks to repository-domain
   categories: service, data and security; user-facing applications; and
   systems, tooling and runtimes.
2. **Develop experts.** Three Qwen3.6-27B-based experts are trained with
   Refresh–Repair–Expand (RRE), alternating agentic reinforcement learning,
   mastery refreshes, and supervised repair on verified successful
   trajectories.
3. **Integrate with MOPD.** A student initialized from Qwen3.6-35B-A3B
   generates its own trajectories and receives token-level guidance from the
   expert corresponding to each training task. The student's initial policy
   serves as the frozen reference for extrapolation.

The final model runs as a single policy. It does not require the three experts
or category routing when deployed.

## Experimental Results

The table shows three-round mean scores (%) for the full model-and-agent
evaluation setups. Improvements are percentage points over Qwen3.6-35B-A3B.

![Logics-SWE benchmark results](results/figures/expanded-eval/model_benchmark_comparison.png)

| Evaluation | Tasks per round | Qwen3.6-35B-A3B | Logics-SWE-Qwen3.6-35B-A3B | Improvement |
| --- | ---: | ---: | ---: | ---: |
| SWE-bench Pro V2 | 642 | 73.31 | **77.00** | **+3.69** |
| SWE-bench Pro V2 Hard-51 | 51 | 28.10 | **33.99** | **+5.88** |
| SWE-bench Multilingual | 300 | 63.44 | **66.44** | **+3.00** |
| SWE-bench Pro | 731 | 48.75 | **51.12** | **+2.37** |
| LiveCodeBench v6 | 175 | 76.95 | **78.10** | **+1.14** |

Hard-51 is a subset of SWE-bench Pro V2. Differences are calculated before
rounding the displayed scores.

## Intended Use

The model is intended for research and development on repository-level software
engineering agents, including codebase exploration, issue diagnosis, code
editing, test execution, and iterative debugging. A coding-agent harness can
provide the model with repository access, tools, execution feedback, and a
workspace in which to build and validate a patch.

## Serving

For a local copy of the model, a vLLM server can be started with:

```bash
vllm serve /path/to/Logics-SWE-Qwen3.6-35B-A3B
```

The server exposes an OpenAI-compatible API for integration with a coding-agent
harness. Use the model's tokenizer and chat template when constructing
requests. See the [Qwen model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
and [vLLM documentation](https://docs.vllm.ai/) for serving setup.

## Data and Resources

The public [Logics-SWE-Env-2.5K](https://huggingface.co/datasets/Logics-MLLM/Logics-SWE-Env-2.5K)
release provides 2,553 software engineering task instances and matching
environment-image references. The [AgenticBigBang repository](https://github.com/alibaba/AgenticBigBang)
contains SWE Labeler, research artifacts, and evaluation materials.

## Citation

If you use this work, please cite:

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

## Acknowledgements

We thank the Qwen, ROLL, R2E-Gym, SWE-agent, SWE-bench, SWE-bench Pro, and
SWE-bench Multilingual contributors, and the research communities behind
MiniRL, MOPD, and ExOPD.

## License

Model license: [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
