"""Stage drivers for the multi-stage PPTSynth task synthesis pipeline.

Each module exposes ``async def run(case_dir: Path, ...) -> StageResult``.
Stages are invoked sequentially by ``synth_one.synth_one``; a failure stops
that paper but does not affect concurrent papers.
"""
from .stage1_profile import run as run_profile
from .stage2_task import run as run_task
from .stage3_rubric import run as run_rubric
from .stage4_audit import run as run_audit
from .stage4b_verify_refine import run as run_verify_refine
from .stage4b_verify_refine import should_trigger as should_trigger_verify_refine
from .stage5_pack import run as run_pack

__all__ = [
    "run_profile", "run_task", "run_rubric", "run_audit",
    "run_verify_refine", "should_trigger_verify_refine", "run_pack",
]
