"""Full-text retrieval for the Reader. Read-only GET. Handles PDF and HTML,
returns extracted plain text (truncated). Never executes fetched content."""
from __future__ import annotations

import io
from bs4 import BeautifulSoup
from ._http import get
from ..schemas import Candidate

MAX_CHARS = 24_000


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:40])
    except Exception:
        return ""


def _html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _arxiv_pdf_url(candidate: Candidate) -> str | None:
    if candidate.source == "arxiv" and candidate.identifier:
        aid = candidate.identifier.split("v")[0]
        return f"https://arxiv.org/pdf/{candidate.identifier}"
    return None


def fetch_text(candidate: Candidate) -> str:
    """Best-effort full text; falls back to the abstract if retrieval fails."""
    urls = []
    pdf = _arxiv_pdf_url(candidate)
    if pdf:
        urls.append(pdf)
    if candidate.url:
        urls.append(candidate.url)
    if candidate.identifier.startswith("10."):
        urls.append(f"https://doi.org/{candidate.identifier}")

    for url in urls:
        try:
            resp = get(url, timeout=30.0)
            if resp.status_code != 200:
                continue
            ctype = resp.headers.get("content-type", "").lower()
            if "pdf" in ctype or url.endswith(".pdf"):
                text = _pdf_text(resp.content)
            else:
                text = _html_text(resp.text)
            if text and len(text.strip()) > 200:
                return text[:MAX_CHARS]
        except Exception:
            continue

    # Fallback: abstract only (clearly labelled so Reader knows fidelity is limited)
    return f"[FULL TEXT UNAVAILABLE — ABSTRACT ONLY]\n{candidate.abstract}"[:MAX_CHARS]
