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


def _arxiv_html_url(candidate: Candidate) -> str | None:
    if candidate.source == "arxiv" and candidate.identifier:
        return f"https://arxiv.org/html/{candidate.identifier}"
    return None


def _arxiv_pdf_url(candidate: Candidate) -> str | None:
    if candidate.source == "arxiv" and candidate.identifier:
        return f"https://arxiv.org/pdf/{candidate.identifier}"
    return None


def fetch_text(candidate: Candidate) -> str:
    """Best-effort full text; falls back to the abstract if retrieval fails.

    HTML is preferred over PDF: HTML extraction is far cleaner than pypdf (which
    mangles multi-column layouts, tables, and math), so the Reader gets more
    faithful text. PDF URLs are tried only after every HTML option fails."""
    html_urls: list[str] = []
    pdf_urls: list[str] = []

    arxiv_html = _arxiv_html_url(candidate)
    if arxiv_html:
        html_urls.append(arxiv_html)
    if candidate.url and not candidate.url.lower().endswith(".pdf"):
        html_urls.append(candidate.url)        # landing/abstract page — usually HTML
    if candidate.identifier.startswith("10."):
        html_urls.append(f"https://doi.org/{candidate.identifier}")  # resolves to HTML

    arxiv_pdf = _arxiv_pdf_url(candidate)
    if arxiv_pdf:
        pdf_urls.append(arxiv_pdf)
    if candidate.url and candidate.url.lower().endswith(".pdf"):
        pdf_urls.append(candidate.url)

    for url in html_urls + pdf_urls:
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
