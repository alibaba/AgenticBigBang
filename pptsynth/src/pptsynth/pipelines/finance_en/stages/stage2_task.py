"""Stage 2: Render Instructions — Finance Doc Card → instructions.md.

The boilerplate Sections 2-6 are mounted into the case dir so the agent can
copy them verbatim. Static checks confirm the result has the expected shape
and that Section 1 does not pre-disclose finance answer values.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._runner import StageOutcome, run_stage
from ..family_registry import FamilyProfile, TITLE_SLIDE_FIELDS
from ..prompt_compose import compose

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_USER_PROMPT = """\
Stage 2: Render Instructions.

Inputs in this working directory:
- ./_paper_card.json   — the only source of document-specific content.
- ./_boilerplate_sections.md — paste verbatim as Sections 2-6.
- ./material.pdf       — open only to disambiguate; trust the Doc Card.

Write a single file ./generation_task/instructions.md following the required
PPTSynth economics instructions style described in your system prompt
(and the appended Domain Context for the title-slide fields).

After writing the file, emit one JSON object as your final assistant message:
{"stage":"task","ok":true,"section_count":<int>,"design_constraint_count":<int>,"byte_size":<int>,"warnings":[]}

Never use Glob/Grep/Read on paths outside the current working directory
(e.g. `..` or absolute parent paths) — parent directories are not readable.
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    boilerplate_src = PROMPTS_DIR / "boilerplate_sections.md"
    boilerplate_dst = case_dir / "_boilerplate_sections.md"
    boilerplate_dst.write_bytes(boilerplate_src.read_bytes())
    (case_dir / "generation_task").mkdir(parents=True, exist_ok=True)


# Words that only ever appear as meta-language about the evaluation pipeline.
_FORBIDDEN_META = [
    "PPTSynth",
    "pptsynth",
    "PPTSYNTH",
    "self-check",
    "Self-check",
    "self check",
    "as required to satisfy",
]


# Anti-pre-disclosure patterns — applied only to Section 1 (the
# document-specific portion). The boilerplate Sections 2-6 are allowed to use
# fixed phrasings (e.g. "at least 5 slides with quantitative details") so we
# deliberately scope the scan to Section 1 only.
_PRE_DISCLOSURE_PATTERNS = [
    # Monetary magnitude: "$62.0 billion", "$8.4bn", "USD 1.2 trillion".
    (
        re.compile(
            r"(?:\$|USD|US\$|€|£|¥)\s?\d[\d,]*(?:\.\d+)?\s*(?:billion|million|trillion|bn|mn)",
            re.IGNORECASE,
        ),
        "monetary value with magnitude",
    ),
    # Any percentage (integer or float): "18%", "2.4 %".
    (re.compile(r"\b\d+(?:\.\d+)?\s*%"), "percentage value"),
    # Growth/direction phrase paired with a number: "up 18", "grew 30".
    (
        re.compile(
            r"\b(?:up|down|grew|rose|fell|increased|decreased|declined|gained|lost)\s+\d",
            re.IGNORECASE,
        ),
        "directional growth value",
    ),
    # Basis points: "50 bps", "25 basis points".
    (re.compile(r"\b\d+\s*(?:bps|basis points)\b", re.IGNORECASE), "basis-point value"),
    # EPS / per-share value: "EPS $2.93", "$0.78 per share".
    (
        re.compile(r"(?:EPS\s*(?:of\s*)?\$?\d|\$\d[\d.]*\s*per share)", re.IGNORECASE),
        "per-share / EPS value",
    ),
]


def _section1_text(text: str) -> str:
    """Slice between '## 1. Content Requirements' and the next '## ' heading."""
    start = text.find("## 1. Content Requirements")
    if start < 0:
        return ""
    rest = text[start:]
    next_heading = re.search(r"\n## (?!1\. Content Requirements)", rest)
    if next_heading:
        return rest[: next_heading.start()]
    return rest


def _static_checks(instructions_path: Path) -> list[str]:
    """Cheap, fast checks. Returns list of issues; empty list = ok."""
    issues: list[str] = []
    if not instructions_path.exists():
        return ["instructions.md not on disk"]
    text = instructions_path.read_text(encoding="utf-8")
    if len(text) < 1500:
        issues.append(f"instructions.md too short ({len(text)} bytes)")
    required_phrases = [
        "Strict Constraints for the Slides",
        "## 1. Content Requirements",
        "## 2. Content Constraints",
        "## 3. Visual & Design",
        "## 4. Text Quality",
        "## 5. Technical Fidelity Requirements",
        "## 6. Presentation Tone and Audience",
        "# **Output Expected**",
    ]
    for ph in required_phrases:
        if ph not in text:
            issues.append(f"missing required section: {ph!r}")
    if "Design Constraint:" not in text:
        issues.append("no Design Constraint: lines (need >=3 across deck)")
    elif text.count("Design Constraint:") < 3:
        issues.append(
            f"only {text.count('Design Constraint:')} Design Constraint: lines (need >=3)"
        )
    for term in _FORBIDDEN_META:
        if term in text:
            issues.append(f"forbidden meta term in instructions.md: {term!r}")
    # Title-slide fields (unified across families).
    for marker in TITLE_SLIDE_FIELDS:
        if marker not in text:
            issues.append(f"title slide missing field: {marker!r}")
    # Page count
    if not re.search(r"must have \*\*\d+-\d+ slides\*\*", text):
        issues.append("missing 'must have **N-M slides**' line")

    # Anti-pre-disclosure: scan only Section 1.
    section1 = _section1_text(text)
    if section1:
        for pattern, label in _PRE_DISCLOSURE_PATTERNS:
            hits = pattern.findall(section1)
            if hits:
                sample = hits[0] if isinstance(hits[0], str) else " ".join(hits[0])
                issues.append(
                    f"Section 1 pre-discloses values ({label}): {sample!r} "
                    f"({len(hits)} hit{'s' if len(hits) != 1 else ''}); "
                    "move specific values to the rubric, keep bullets topical"
                )
    return issues


_RESUME_PROMPT_TEMPLATE = """\
Your previous attempt in this session FAILED harness validation:

{error}

Fix the existing artifact IN PLACE with minimal targeted edits (do not
regenerate it from scratch, do not re-read material.pdf unless strictly
necessary). The error list above may be TRUNCATED — after fixing the listed
violations, re-check the ENTIRE artifact against the mounted schema (every
object at every level: exact required field names, no additional properties)
and fix all remaining violations of the same kind. Then finish exactly as
originally instructed, emitting the same final JSON message format.
"""

async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 20,
    timeout_s: int = 1200,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
    effort: str | None = None,
    retry_hint: str | None = None,
    resume_session_id: str | None = None,
    family_profile: FamilyProfile | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    base_system = PROMPTS_DIR / "2_task_system.md"
    system_prompt_file = compose("2_task", base_system, case_dir, family_profile)
    if resume_session_id:
        user_prompt = _RESUME_PROMPT_TEMPLATE.format(error=retry_hint or "unknown error")
    else:
        user_prompt = _USER_PROMPT
        if retry_hint:
            user_prompt += (
                "\n\nPREVIOUS ATTEMPT FAILED with this harness error — do not repeat it:\n"
                + retry_hint + "\n"
            )
    out = await run_stage(
        stage_name="2_task",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=user_prompt,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
        effort=effort,
        resume_session_id=resume_session_id,
    )
    # The on-disk artifact is the source of truth: if instructions.md exists
    # and passes static checks, the stage succeeded even when the CLI exited
    # non-zero (salvage — mirrors stage3/stage4 behaviour).
    instr = case_dir / "generation_task" / "instructions.md"
    if not out.ok and not instr.exists():
        return out
    issues = _static_checks(instr)
    if issues:
        out.ok = False
        out.error = "instructions.md static checks: " + "; ".join(issues[:6])
    else:
        out.ok = True
        out.error = None
    return out
