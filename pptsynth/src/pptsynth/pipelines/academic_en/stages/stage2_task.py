"""Stage 2: Render Instructions — Paper Card → instructions.md.

The boilerplate Sections 2-6 are mounted into the case dir so the agent can
copy them verbatim. Static checks confirm the result has the expected
shape.
"""
from __future__ import annotations

import re
from pathlib import Path

from ._runner import StageOutcome, run_stage

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_USER_PROMPT = """\
Stage 2: Render Instructions.

Inputs in this working directory:
- ./_paper_card.json   — the only source of paper-specific content.
- ./_boilerplate_sections.md — paste verbatim as Sections 2-6.
- ./material.pdf       — open only to disambiguate; trust the Paper Card.

Write a single file ./generation_task/instructions.md following the
PPTSynth academic instructions style described in your
system prompt.

After writing the file, emit one JSON object as your final assistant
message with shape:
{"stage":"task","ok":true,"section_count":<int>,"design_constraint_count":<int>,"byte_size":<int>,"warnings":[]}
"""


def _ensure_workspace_files(case_dir: Path) -> None:
    boilerplate_src = PROMPTS_DIR / "boilerplate_sections.md"
    boilerplate_dst = case_dir / "_boilerplate_sections.md"
    boilerplate_dst.write_bytes(boilerplate_src.read_bytes())
    (case_dir / "generation_task").mkdir(parents=True, exist_ok=True)


# Words that *only* ever appear as meta-language about the evaluation
# pipeline. These are safe hard bans because no academic paper title or
# legitimate slide content uses them. (Words like "benchmark", "rubric",
# "checklist" are *not* on this list — they appear in many real paper
# titles and bodies. Stage 4 (audit) catches their meta-language abuse.)
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
# paper-specific portion). The boilerplate Sections 2-6 are allowed to
# use these patterns in fixed phrasings (e.g. "at least 5 slides with
# quantitative details") so we deliberately scope the scan.
_PRE_DISCLOSURE_PATTERNS = [
    # Floating-point percentage (e.g. "90.3%", "62.9 %"). The "\d+\."
    # leading lookahead prevents matching plain integers like "5%".
    (re.compile(r"\b\d+\.\d+\s*%"), "floating-point percentage"),
    # Numerical comparison phrase: "<num> versus/vs/over/surpassing/beating <num>"
    (
        re.compile(
            r"\b\d+(?:\.\d+)?\s+(?:versus|vs\.?|over|surpassing|beating)\s+(?:[A-Za-z][\w\-]*\s+)?\d+(?:\.\d+)?",
            re.IGNORECASE,
        ),
        "numerical baseline comparison",
    ),
    # Signed delta on a metric: "+17.1 AP", "-4.2 EM", etc.
    # The lookbehind `(?<![A-Za-z])` rejects matches where the sign
    # is the internal dash of a dataset/version token like
    # `CIFAR-10 Accuracy`, `ImageNet-1K accuracy`, `COCO-2017 mAP`
    # — there the `-10` is part of the dataset name, not a delta.
    (
        re.compile(
            r"(?<![A-Za-z])[+\-]\s?\d+(?:\.\d+)?\s+(?:AP|mAP|EM|F1|CIDEr|BLEU|ROUGE|METEOR|accuracy|acc)\b",
            re.IGNORECASE,
        ),
        "signed metric delta",
    ),
    # Metric followed by a specific score: "CIDEr 97.9", "EM 30.4",
    # "mAP 78.0". Caught only with a decimal value to avoid the
    # boilerplate "5 slides".
    (
        re.compile(
            r"\b(?:AP|mAP|EM|F1|CIDEr|BLEU|ROUGE|METEOR|accuracy|acc)\s+\d+\.\d+\b",
            re.IGNORECASE,
        ),
        "metric paired with specific score",
    ),
    # Architecture / hyperparameter assignment in subscripted form:
    # "N_v = 784", "N_h = 50", "d_model = 1024". Surgical: requires
    # uppercase + underscore subscript so it does NOT match
    # algorithm-name parameters like "k = 2" that legitimately
    # appear as method labels (e.g. "k=2 Subproblem").
    (
        re.compile(r"\b[A-Z]_[A-Za-z0-9]+\s*=\s*\d+\b"),
        "architecture / hyperparameter assignment",
    ),
    # Layer-size leakage by phrase: "784 visible neurons",
    # "50 hidden neurons", "12 attention heads", "1024 dimensional".
    (
        re.compile(
            r"\b\d+\s+(?:visible|hidden|attention|input|output|latent)\s+(?:neurons?|units?|heads?|layers?|channels?|dimensions?)\b",
            re.IGNORECASE,
        ),
        "explicit layer/architecture dimension",
    ),
    # Asymptotic complexity expression as bullet payload:
    # "O(nr + rk^2 + k^3)", "O(1/epsilon)", "O(1/ε)". Allows benign
    # `O(...)` only if the bullet does NOT carry it as content —
    # but in practice any O(...) inside Section 1 means the deck has
    # been handed the bound. Cheaper to reject and let Stage 1 retry
    # in scope-shape.
    (
        re.compile(r"\bO\([^)]+\)"),
        "asymptotic complexity expression",
    ),
]


def _section1_text(text: str) -> str:
    """Slice between '## 1. Content Requirements' and the next '## ' heading."""
    start = text.find("## 1. Content Requirements")
    if start < 0:
        return ""
    rest = text[start:]
    # Find the next '## ' heading after the start.
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
    # Required structural anchors
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
    # Forbidden meta language anywhere in the file
    for term in _FORBIDDEN_META:
        if term in text:
            issues.append(f"forbidden meta term in instructions.md: {term!r}")
    # Title-slide bullet shape
    for marker in ["Paper Title:", "Author Team:", "Affiliation:", "Conference:"]:
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


async def run(
    *,
    case_slug: str,
    case_dir: Path,
    model: str | None = None,
    max_turns: int = 20,
    timeout_s: int = 1200,
    max_budget_usd: float | None = None,
    max_thinking_tokens: int | None = None,
) -> StageOutcome:
    _ensure_workspace_files(case_dir)
    system_prompt_file = PROMPTS_DIR / "2_task_system.md"
    out = await run_stage(
        stage_name="2_task",
        case_slug=case_slug,
        case_dir=case_dir,
        user_prompt=_USER_PROMPT,
        system_prompt_file=system_prompt_file,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        max_turns=max_turns,
        timeout_s=timeout_s,
        model=model,
        max_budget_usd=max_budget_usd,
        max_thinking_tokens=max_thinking_tokens,
    )
    if not out.ok:
        return out

    issues = _static_checks(case_dir / "generation_task" / "instructions.md")
    if issues:
        out.ok = False
        out.error = "instructions.md static checks: " + "; ".join(issues[:6])
    return out
