"""
PDF parsing into page-cited passages.

Text is extracted with Poppler's `pdftotext` (the same engine many Python PDF libraries wrap; install it
with `apt install poppler-utils`). pdftotext separates pages with a form feed, so each passage keeps
the page number it came from, and every answer can cite "document, page N".
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

CHUNK_CHARS = 1100
OVERLAP_CHARS = 180


class PdfError(RuntimeError):
    pass


def pdftotext_available() -> bool:
    return shutil.which("pdftotext") is not None


def extract_pages(path: Path, timeout: int = 120) -> list[str]:
    if not pdftotext_available():
        raise PdfError("pdftotext not found: install poppler-utils (apt install poppler-utils)")
    try:
        res = subprocess.run(["pdftotext", "-enc", "UTF-8", "-q", str(path), "-"], capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as e:
        raise PdfError(f"pdftotext timed out on {path.name}") from e
    if res.returncode not in (0, 1) or not res.stdout:
        raise PdfError(f"pdftotext failed on {path.name}: {res.stderr.decode('utf-8', 'replace')[:200]}")
    pages = res.stdout.decode("utf-8", "replace").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def clean(text: str) -> str:
    t = text.replace("­", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)              # de-hyphenate line breaks: "com-\nbustion"
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\.{4,}", " ", t)                       # table-of-contents leaders
    t = re.sub(r"\s*\n\s*", "\n", t)
    # Join wrapped lines inside sentences; keep breaks after sentence ends and before list items or bullets.
    t = re.sub(r"(?<![.:;!?])\n(?!\s*(?:\(?\d{1,2}[.)]\s|[•●▪◦\-–]\s))", " ", t)
    return t.strip()


def _good(text: str) -> bool:
    letters = sum(ch.isalpha() for ch in text)
    return len(text) >= 80 and letters / max(1, len(text)) > 0.45


def chunk_pages(pages: list[str]) -> list[dict]:
    """Split each page into ~1,100-character passages on sentence/line boundaries, with overlap; never across pages."""
    out = []
    for pno, raw in enumerate(pages, start=1):
        text = clean(raw)
        if not _good(text):
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_CHARS)
            if end < len(text):
                cut = max(text.rfind(". ", start + CHUNK_CHARS // 2, end), text.rfind("\n", start + CHUNK_CHARS // 2, end))
                if cut > start:
                    end = cut + 1
            piece = text[start:end].strip()
            if _good(piece):
                out.append({"page": pno, "text": piece})
            if end >= len(text):
                break
            start = max(end - OVERLAP_CHARS, start + 1)
            nxt = text.find(" ", start)
            start = nxt + 1 if 0 <= nxt < end else start
    return out


def title_from_file(accession: str, file_name: str) -> str:
    t = re.sub(rf"^{re.escape(accession)}_", "", file_name)
    t = re.sub(r"\.pdf$", "", t, flags=re.I)
    t = re.sub(r"^(Reports|Science Documents|Engineering Documents|Presentations|Reference Data|Analyzed Data|Raw Data)_", "", t)
    return re.sub(r"[_]+", " ", t).strip(" .") or file_name
