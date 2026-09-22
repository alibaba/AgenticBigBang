"""Discover finance PDFs from the delivery index.csv and assign stable slugs.

The finance corpus is laid out as:
    <data_root>/delivery/<sha256>/material.pdf
    <data_root>/delivery/index.csv    (2000 rows, one per document)

index.csv columns:
    sha256, family, sub_genre_hint, channel, ticker, company, sector_norm,
    institution, series, country, year, quarter, pages, orientation,
    has_charts, richness, value_token_count, distinct_metric_hits, url,
    material_path

`material_path` is relative to <data_root> (e.g. "delivery/<sha>/material.pdf").

Slugs are deterministic across reruns:
  Family A:  <ticker-or-company>_<year><quarter>_<sha8>
  Family B:  <institution>_<series>_<country-or-year>_<sha8>
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


@dataclass(frozen=True)
class Doc:
    pdf_path: Path
    slug: str
    sha256: str
    family: str          # "A" | "B"
    sub_genre: str
    issuer: str
    reporting_period: str
    sector: str
    pages: int


def _ascii(text: str, *, max_len: int = 28) -> str:
    s = _NON_ALNUM.sub("_", (text or "").strip()).strip("_").lower()
    return s[:max_len].strip("_")


def _make_slug(row: dict, sha8: str) -> str:
    family = (row.get("family") or "A").strip().upper()
    if family == "B":
        inst = _ascii(row.get("institution") or "inst", max_len=20)
        series = _ascii(row.get("series") or row.get("sub_genre_hint") or "series", max_len=24)
        tail = _ascii(row.get("country") or row.get("year") or "", max_len=12)
        parts = [p for p in (inst, series, tail) if p]
    else:
        head = _ascii(row.get("ticker") or row.get("company") or "issuer", max_len=24)
        year = _ascii(row.get("year") or "", max_len=6)
        quarter = _ascii(row.get("quarter") or "", max_len=6)
        period = "".join(p for p in (year, quarter) if p)
        parts = [p for p in (head, period) if p]
    stem = "_".join(parts) or "doc"
    return f"{stem}_{sha8}"


def _reporting_period(row: dict) -> str:
    family = (row.get("family") or "A").strip().upper()
    if family == "B":
        bits = [row.get("series"), row.get("country"), row.get("year")]
        return " ".join(b for b in bits if b) or (row.get("sub_genre_hint") or "")
    bits = [row.get("year"), row.get("quarter")]
    return " ".join(b for b in bits if b)


def _issuer(row: dict) -> str:
    family = (row.get("family") or "A").strip().upper()
    if family == "B":
        return row.get("institution") or row.get("series") or "institution"
    return row.get("company") or row.get("ticker") or "issuer"


def discover_from_csv(index_csv: Path, data_root: Path) -> list[Doc]:
    """Read index.csv and return one Doc per resolvable material.pdf."""
    docs: list[Doc] = []
    seen: set[str] = set()
    with index_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sha = (row.get("sha256") or "").strip()
            if not sha:
                continue
            rel = (row.get("material_path") or f"delivery/{sha}/material.pdf").strip()
            pdf_path = (data_root / rel).resolve()
            if not pdf_path.exists():
                # Fall back to <data_root>/delivery/<sha>/material.pdf
                alt = (data_root / "delivery" / sha / "material.pdf").resolve()
                if alt.exists():
                    pdf_path = alt
                else:
                    continue
            sha8 = sha[:8]
            slug = _make_slug(row, sha8)
            original = slug
            salt = 1
            while slug in seen:
                salt += 1
                slug = f"{original}_{salt}"
            seen.add(slug)
            try:
                pages = int(float(row.get("pages") or 0))
            except (TypeError, ValueError):
                pages = 0
            docs.append(
                Doc(
                    pdf_path=pdf_path,
                    slug=slug,
                    sha256=sha,
                    family=(row.get("family") or "A").strip().upper() or "A",
                    sub_genre=(row.get("sub_genre_hint") or "").strip(),
                    issuer=_issuer(row).strip(),
                    reporting_period=_reporting_period(row).strip(),
                    sector=(row.get("sector_norm") or "").strip(),
                    pages=pages,
                )
            )
    return docs
