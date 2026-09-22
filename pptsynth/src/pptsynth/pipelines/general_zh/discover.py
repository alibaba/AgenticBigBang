"""Discover input PDFs and assign stable, reproducible case slugs.

Filename convention for labeled inputs:
    <input_root>/<一级领域>/<一级>_<二级>_<suffix>.pdf
    where <suffix> is either a sequential index (legacy) or a raw_id hash (v4+).

Examples:
    <input_root>/医疗健康/医疗健康_病例分享_1.pdf              (legacy)
    <input_root>/医疗健康/医疗健康_病例分享_e4356cb4b4417e5e.pdf  (raw id)
      → primary="医疗健康", secondary="病例分享", slug="yi_liao_jian_kang_bing_li_fen_xiang_e4356cb4"

Slug strategy:
1. If filename matches <primary>_<secondary>_<suffix>.pdf, extract components.
2. Transliterate via pypinyin (if available) or fall back to sha1 hash.
3. Long suffixes (>8 chars, e.g. raw_id) are truncated for slug readability.
4. Slug is deterministic across reruns.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")
_BROAD_DOMAIN_RE = re.compile(r"^(.+?)_(.+?)_(.+)\.pdf$")
_V2_SUFFIX_RE = re.compile(r"_v\d+$")


@dataclass(frozen=True)
class Paper:
    pdf_path: Path
    slug: str
    primary: str    # 一级领域
    secondary: str  # 二级领域


def _pinyin_slug(text: str, *, max_len: int = 60) -> str | None:
    """Best-effort pinyin transliteration. Returns None if pypinyin absent."""
    try:
        from pypinyin import lazy_pinyin  # type: ignore[import-not-found]
    except ImportError:
        return None
    parts = lazy_pinyin(text)
    joined = "_".join(p for p in parts if p)
    cleaned = _NON_ALNUM.sub("_", joined).strip("_").lower()
    return cleaned[:max_len] if cleaned else None


def _hash_slug(text: str, *, length: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def _ascii_slug(stem: str, *, max_len: int = 60) -> str:
    s = _NON_ALNUM.sub("_", stem).strip("_").lower()
    return (s or "doc")[:max_len]


def make_slug(pdf_path: Path) -> tuple[str, str, str]:
    """Return (slug, primary, secondary) for a broad-domain PDF.

    Falls back gracefully when filename doesn't match the convention.
    """
    name = pdf_path.name
    m = _BROAD_DOMAIN_RE.match(name)
    if m:
        primary_raw, secondary_raw, suffix = m.group(1), m.group(2), m.group(3)
        # Strip _v2 / _v3 suffix from secondary (batch-2+ downloads)
        secondary_raw = _V2_SUFFIX_RE.sub("", secondary_raw)
        # Truncate long suffixes (e.g. 32-char raw_id) for slug readability
        suffix_short = suffix if len(suffix) <= 8 else suffix[:8]
        combined = f"{primary_raw}_{secondary_raw}_{suffix_short}"
        pinyin = _pinyin_slug(combined)
        if pinyin:
            slug = pinyin
        else:
            h = _hash_slug(combined)
            slug = f"{_ascii_slug(combined, max_len=52)}_{h}"
        return slug, primary_raw, secondary_raw

    # Fallback: try to infer primary from parent dir name
    parent_name = pdf_path.parent.name
    primary_raw = parent_name if parent_name else "unknown"
    secondary_raw = "unknown"
    stem = pdf_path.stem
    h = _hash_slug(str(pdf_path))
    pinyin = _pinyin_slug(stem)
    if pinyin:
        slug = f"{pinyin}_{h[:6]}"
    else:
        slug = f"{_ascii_slug(stem, max_len=52)}_{h}"
    return slug, primary_raw, secondary_raw


def discover_pdfs(pdf_dir: Path, *, recursive: bool = True) -> list[Paper]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdfs = sorted(pdf_dir.glob(pattern))
    seen: set[str] = set()
    out: list[Paper] = []
    for p in pdfs:
        slug, primary, secondary = make_slug(p)
        original = slug
        salt = 1
        while slug in seen:
            salt += 1
            slug = f"{original}_{salt}"
        seen.add(slug)
        out.append(Paper(pdf_path=p, slug=slug, primary=primary, secondary=secondary))
    return out
