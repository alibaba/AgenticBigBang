"""Discover sinoconf input PDFs and assign stable, reproducible case slugs.

Slug strategy for sinoconf papers (filename pattern:
``paper_<id>_<rank>._<Chinese title>.pdf``):

1. Extract the ``<id>_<rank>`` pair as a stable numeric identifier.
2. Transliterate the Chinese title portion to pinyin (if pypinyin is
   available) or fall back to a sha1 hash, truncated to keep slugs
   short and filesystem-safe.
3. Final slug: ``<id>_<rank>_<pinyin_or_hash>``, deterministic across
   reruns and PDF subsets.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_SINOCONF_ID_RE = re.compile(r"^paper_(\d+)_(\d+)\._")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


@dataclass(frozen=True)
class Paper:
    pdf_path: Path
    slug: str


def _pinyin_slug(chinese: str, *, max_len: int = 48) -> str | None:
    """Best-effort pinyin transliteration. Returns None if pypinyin is absent."""
    try:
        from pypinyin import lazy_pinyin  # type: ignore[import-not-found]
    except ImportError:
        return None
    parts = lazy_pinyin(chinese)
    joined = "_".join(parts)
    cleaned = _NON_ALNUM.sub("_", joined).strip("_").lower()
    return cleaned[:max_len] if cleaned else None


def _hash_slug(text: str, *, length: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def make_slug(pdf_path: Path) -> str:
    name = pdf_path.name
    m = _SINOCONF_ID_RE.match(name)
    if m:
        paper_id, rank = m.group(1), m.group(2)
        prefix = f"{paper_id}_{rank}"
        title_part = name[m.end():].rstrip(".pdf").rstrip(".")
        pinyin = _pinyin_slug(title_part)
        if pinyin:
            return f"{prefix}_{pinyin}"
        return f"{prefix}_{_hash_slug(title_part)}"
    # Fallback for non-standard filenames
    h = _hash_slug(str(pdf_path))
    stem = _NON_ALNUM.sub("_", pdf_path.stem).strip("_").lower()[:52]
    return f"{stem}_{h}" if stem else h


def discover_pdfs(pdf_dir: Path, *, recursive: bool = True) -> list[Paper]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdfs = sorted(pdf_dir.glob(pattern))
    seen: set[str] = set()
    out: list[Paper] = []
    for p in pdfs:
        slug = make_slug(p)
        original = slug
        salt = 1
        while slug in seen:
            salt += 1
            slug = f"{original}_{salt}"
        seen.add(slug)
        out.append(Paper(pdf_path=p, slug=slug))
    return out
