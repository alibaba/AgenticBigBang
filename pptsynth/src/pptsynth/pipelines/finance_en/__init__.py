"""PPTSynth economics/finance task synthesis pipeline (econ_synth).

One finance-document PDF → one case directory containing material.pdf,
generation_task/{instructions.md, judge_prompt.json, statistics.yaml},
_paper_card.json (a finance Doc Card), _audit_report.json, research_notes.md,
_case_meta.json, and per-stage logs. Cases are written under
``<out_root>/finance_en/<slug>/``; shared common_judge_prompt.json +
judge_weights.yaml are copied once to ``<out_root>/finance_en/``.

Pipeline (each stage is its own ``claude -p`` subprocess in the case dir):

    Stage 1  PROFILE        → _paper_card.json (finance Doc Card) + research_notes.md
    Stage 2  TASK           → generation_task/instructions.md
    Stage 3  RUBRIC         → generation_task/judge_prompt.json
    Stage 4  AUDIT          → _audit_report.json + in-place fixes
    Stage 4b VERIFY-REFINE  → revised judge_prompt.json + _verify_refine_report.json
                              (conditional: only when audit scores trigger it)
    Stage 5  PACK           → generation_task/statistics.yaml + case_status.json

The document family (A = corporate disclosure, B = macro flagship) is read from
delivery/index.csv and injected into every LLM stage's system prompt.
"""
from .discover import Doc, discover_from_csv
from .family_registry import FamilyProfile, load_for_doc
from .synth_one import CaseResult, serialize_case_result, synth_one

__all__ = [
    "Doc",
    "FamilyProfile",
    "CaseResult",
    "discover_from_csv",
    "load_for_doc",
    "serialize_case_result",
    "synth_one",
]
