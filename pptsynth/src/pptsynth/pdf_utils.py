"""Small, permissively licensed PDF-reading helpers used by PPTSynth."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_text_sample(pdf_path: Path, *, max_chars: int) -> str:
    """Extract a bounded sample from the beginning and end of a text PDF."""
    try:
        with pdf_path.open("rb") as stream:
            reader = PdfReader(stream, strict=False)
            page_count = len(reader.pages)
            indices = list(range(min(6, page_count)))
            if page_count > 8:
                indices.extend(range(max(6, page_count - 2), page_count))
            chunks: list[str] = []
            remaining = max_chars
            for index in dict.fromkeys(indices):
                text = reader.pages[index].extract_text() or ""
                text = text.strip()
                if not text:
                    continue
                part = f"\n\n--- page {index + 1} ---\n{text}"
                chunks.append(part[:remaining])
                remaining -= len(part)
                if remaining <= 0:
                    break
            return "".join(chunks).strip()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"cannot read PDF: {exc}") from exc


def page_count(pdf_path: Path) -> int:
    """Return the PDF page count, or zero when the document cannot be read."""
    try:
        with pdf_path.open("rb") as stream:
            return len(PdfReader(stream, strict=False).pages)
    except Exception:  # noqa: BLE001
        return 0
