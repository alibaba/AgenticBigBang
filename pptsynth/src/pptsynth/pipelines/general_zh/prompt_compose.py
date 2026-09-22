"""Compose per-case system prompts by appending domain context to base templates.

Usage:
    path = compose("1_profile", base_prompt_file, case_dir, domain_pack)
    # path is case_dir / "_system_1_profile.md"

The composed file is written to the case directory so the claude subprocess
(which has cwd=case_dir) could read it if needed, and the path is passed
directly to --append-system-prompt-file.
"""
from __future__ import annotations

from pathlib import Path

from .domain_registry import DomainPack


def compose(
    stage_name: str,
    base_prompt_file: Path,
    case_dir: Path,
    domain_pack: DomainPack | None,
) -> Path:
    """Return path to a composed system prompt for this stage + domain.

    If domain_pack is None, returns base_prompt_file unchanged (no copy).
    Otherwise writes base + domain context to case_dir/_system_<stage_name>.md
    and returns that path.
    """
    if domain_pack is None:
        return base_prompt_file

    base_text = base_prompt_file.read_text(encoding="utf-8")
    domain_text = domain_pack.context_text()
    composed = base_text.rstrip() + "\n\n" + domain_text + "\n"

    out_path = case_dir / f"_system_{stage_name}.md"
    out_path.write_text(composed, encoding="utf-8")
    return out_path
