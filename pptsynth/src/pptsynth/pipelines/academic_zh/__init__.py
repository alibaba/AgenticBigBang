"""Sinoconf 中文学术论文 PPTSynth 任务合成管线。

合并自 pptsynth_synth_rubricsrefineAB2（rubrics 质量底座）和
sinoconf_synth_rubrics_v3（中文多学科适配）。

一篇论文 PDF → 一个案例目录，包含 material.pdf、generation_task/
{instructions.md, judge_prompt.json, statistics.yaml}、_paper_card.json、
_audit_report.json、research_notes.md 和逐阶段日志。

管线（每阶段在独立 ``claude -p`` 子进程中运行）：

    Stage 1  PROFILE        → _paper_card.json + research_notes.md
    Stage 2  TASK           → generation_task/instructions.md
    Stage 3  RUBRIC         → generation_task/judge_prompt.json
    Stage 4  AUDIT          → _audit_report.json + 就地修复（11轴）
    Stage 4b VERIFY-REFINE  → 修订后的 judge_prompt.json + _verify_refine_report.json
                              （条件式：仅当审计评分触发时运行）
    Stage 5  PACK           → generation_task/statistics.yaml + case_status.json
                              （确定性；无 LLM）
"""
from .discover import Paper, discover_pdfs, make_slug
from .synth_one import CaseResult, serialize_case_result, synth_one

__all__ = [
    "Paper",
    "CaseResult",
    "discover_pdfs",
    "make_slug",
    "serialize_case_result",
    "synth_one",
]
