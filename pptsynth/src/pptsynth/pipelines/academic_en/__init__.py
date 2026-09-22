"""PPTSynth academic task synthesis pipeline.

One paper PDF → one case directory containing material.pdf, generation_task/
{instructions.md, judge_prompt.json, statistics.yaml}, _paper_card.json,
_audit_report.json, research_notes.md, and per-stage logs.

Pipeline (each stage is its own ``claude -p`` subprocess in the case dir):

    Stage 1  PROFILE        → _paper_card.json + research_notes.md
    Stage 2  TASK           → generation_task/instructions.md
    Stage 3  RUBRIC         → generation_task/judge_prompt.json
    Stage 4  AUDIT          → _audit_report.json + in-place fixes
    Stage 4b VERIFY-REFINE  → revised judge_prompt.json + _verify_refine_report.json
                              (conditional: only when audit scores trigger it)
    Stage 5  PACK           → generation_task/statistics.yaml + case_status.json
                              (deterministic; no LLM)

Sessions are isolated by ``cwd=case_dir`` + ``--no-session-persistence``
+ ``--bare``. Cases run concurrently up to a configured semaphore.
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
