"""LLM-first, auditable routing for PPTSynth input PDFs."""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .pdf_utils import extract_text_sample


PROFILE_CHOICES = ("academic_en", "academic_zh", "finance_en", "general_zh")
DEFAULT_GENERAL_PRIMARY = "通用文档"
DEFAULT_GENERAL_SECONDARY = "通用文档"


@dataclass(frozen=True)
class Route:
    profile: str
    language: str
    confidence: float
    primary: str = DEFAULT_GENERAL_PRIMARY
    secondary: str = DEFAULT_GENERAL_SECONDARY
    finance_family: str = "A"
    finance_sub_genre: str = ""
    issuer: str = ""
    reporting_period: str = ""
    sector: str = ""
    rationale: str = ""
    source: str = "llm"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_pdf_text(pdf_path: Path, *, max_chars: int = 24000) -> str:
    """Extract a bounded, representative text sample without copying the PDF."""
    return extract_text_sample(pdf_path, max_chars=max_chars)


def _taxonomy_text() -> str:
    root = Path(__file__).parent / "pipelines" / "general_zh" / "domains"
    groups: list[str] = []
    for primary_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        secondaries = sorted(p.stem for p in primary_dir.glob("*.yaml") if p.name != "_base.yaml")
        groups.append(f"{primary_dir.name}: " + ", ".join(secondaries))
    return "\n".join(groups)


def _router_prompt(pdf_name: str, excerpt: str) -> str:
    return f"""You route PDF source material to a PPTSynth synthesis profile. Return exactly one JSON object, without markdown.

Allowed profiles:
- academic_en: an English research paper intended for an academic presentation.
- academic_zh: a Chinese research paper intended for an academic presentation.
- finance_en: an English corporate disclosure, financial report, earnings release, investor document, or macroeconomic report.
- general_zh: other material. This is also the required fallback for uncertain or unsupported material.

Required JSON keys:
{{
  "profile": one allowed profile,
  "language": "en"|"zh"|"other",
  "confidence": number from 0 to 1,
  "primary": Chinese general-domain primary label or "通用文档",
  "secondary": Chinese general-domain secondary label or "通用文档",
  "finance_family": "A" for company disclosures or "B" for macro/institutional reports,
  "finance_sub_genre": short ASCII-or-English label,
  "issuer": issuer/institution when evident, otherwise "",
  "reporting_period": reporting period when evident, otherwise "",
  "sector": sector when evident, otherwise "",
  "rationale": one short sentence
}}

For general_zh, choose the closest taxonomy label below when supported; otherwise use 通用文档 for both labels.
{_taxonomy_text()}

PDF filename: {pdf_name}
Extracted text follows:
---
{excerpt or "[No extractable text; use general_zh with low confidence.]"}
---
"""


def _parse_route(data: dict[str, Any], *, source: str) -> Route:
    profile = str(data.get("profile", "general_zh"))
    if profile not in PROFILE_CHOICES:
        profile = "general_zh"
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))
    primary = str(data.get("primary") or DEFAULT_GENERAL_PRIMARY)
    secondary = str(data.get("secondary") or DEFAULT_GENERAL_SECONDARY)
    if profile != "general_zh":
        primary, secondary = DEFAULT_GENERAL_PRIMARY, DEFAULT_GENERAL_SECONDARY
    family = str(data.get("finance_family") or "A").upper()
    if family not in {"A", "B"}:
        family = "A"
    return Route(
        profile=profile,
        language=str(data.get("language") or "other"),
        confidence=confidence,
        primary=primary,
        secondary=secondary,
        finance_family=family,
        finance_sub_genre=str(data.get("finance_sub_genre") or ""),
        issuer=str(data.get("issuer") or ""),
        reporting_period=str(data.get("reporting_period") or ""),
        sector=str(data.get("sector") or ""),
        rationale=str(data.get("rationale") or ""),
        source=source,
    )


def overridden_route(profile: str) -> Route:
    if profile not in PROFILE_CHOICES:
        raise ValueError(f"unsupported route override: {profile}")
    return Route(
        profile=profile,
        language="zh" if profile.endswith("zh") else "en",
        confidence=1.0,
        source="override",
        rationale="Selected by --route.",
    )


def route_pdf(pdf_path: Path, *, model: str | None = None) -> Route:
    """Ask the locally configured Claude CLI for one schema-shaped route."""
    excerpt = extract_pdf_text(pdf_path)
    cmd = [
        "claude", "-p", _router_prompt(pdf_path.name, excerpt),
        "--output-format", "json", "--max-turns", "1", "--bare",
        "--no-session-persistence", "--setting-sources", "project,local",
    ]
    if model:
        cmd += ["--model", model]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as exc:
        raise RuntimeError("Claude Code CLI is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("router model call timed out") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"router model call failed: {completed.stderr[-500:].strip()}")
    try:
        envelope = json.loads(completed.stdout)
        raw = envelope.get("result", "")
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise RuntimeError("router did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("router result is not a JSON object")
    route = _parse_route(payload, source="llm")
    if route.confidence < 0.5:
        return Route(
            profile="general_zh", language=route.language, confidence=route.confidence,
            rationale=f"Low-confidence route fallback. {route.rationale}", source="fallback",
        )
    return route
