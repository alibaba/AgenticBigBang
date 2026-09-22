"""Discover input PDFs and assign stable, reproducible case slugs.

Slug strategy:
1. If the filename ends in `[<8-or-10-char-id>].pdf` (the OpenReview pattern
   used in ICLR / NeurIPS exports), use that id directly. This is the most
   stable choice — the slug stays the same across reruns and across
   different PDF subsets.
2. Otherwise, derive a slug by ASCII-ifying the filename stem and taking up
   to 60 chars; collisions get a short hash suffix so the slug stays
   deterministic.

We do **not** prefix slugs with running indices. Running-indices were the
discover.py bug we are fixing: rerunning on a different PDF subset
silently renamed cases.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_OPENREVIEW_ID_RE = re.compile(r"\[([A-Za-z0-9]{8,12})\]\.pdf$")
_NON_ASCII_ALNUM = re.compile(r"[^A-Za-z0-9]+")


@dataclass(frozen=True)
class Paper:
    pdf_path: Path
    slug: str


def _ascii_slug(stem: str, *, max_len: int = 60) -> str:
    s = _NON_ASCII_ALNUM.sub("_", stem).strip("_").lower()
    if not s:
        s = "paper"
    return s[:max_len]


def make_slug(pdf_path: Path) -> str:
    """Return a deterministic slug for one PDF file.

    Uses the OpenReview id if present; otherwise a short hash + ascii
    prefix.
    """
    name = pdf_path.name
    m = _OPENREVIEW_ID_RE.search(name)
    if m:
        # The OpenReview id alone is unique but unreadable; prepend a few
        # ascii words from the title so directory listings remain useful.
        rid = m.group(1)
        head = _ascii_slug(name[: m.start()].rstrip(" _-"), max_len=48)
        return f"{head}_{rid}" if head else rid
    # Hash-suffix slug for stability when filenames differ only in
    # punctuation / case.
    h = hashlib.sha1(str(pdf_path).encode("utf-8")).hexdigest()[:8]
    head = _ascii_slug(pdf_path.stem, max_len=52)
    return f"{head}_{h}"


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
