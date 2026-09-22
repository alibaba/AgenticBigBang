"""Compose per-case system prompts by appending finance Domain Context.

Usage:
    path = compose("1_profile", base_prompt_file, case_dir, family_profile)
    # path is case_dir / "_system_1_profile.md" (or the base file if no profile)

The composed file is written into the case directory so the isolated
``claude -p`` subprocess (cwd=case_dir) can also read it if needed, and the
path is passed to ``--append-system-prompt-file``.
"""
from __future__ import annotations

from pathlib import Path

from .family_registry import FamilyProfile


def compose(
    stage_name: str,
    base_prompt_file: Path,
    case_dir: Path,
    family_profile: FamilyProfile | None,
) -> Path:
    if family_profile is None:
        return base_prompt_file
    base_text = base_prompt_file.read_text(encoding="utf-8")
    composed = base_text.rstrip() + "\n\n" + family_profile.context_text() + "\n"
    out_path = case_dir / f"_system_{stage_name}.md"
    out_path.write_text(composed, encoding="utf-8")
    return out_path
