"""Web search for grey literature (lab blogs, technical reports). Read-only.
Uses the keyless DuckDuckGo HTML endpoint; degrades gracefully to [] if blocked."""
from __future__ import annotations

import re
from urllib.parse import unquote
from typing import List
from bs4 import BeautifulSoup
from ..schemas import Candidate
from ._http import get

ENDPOINT = "https://html.duckduckgo.com/html/"


def _clean_ddg_url(href: str) -> str:
    m = re.search(r"uddg=([^&]+)", href)
    return unquote(m.group(1)) if m else href


def search(terms: List[str], max_results: int = 15) -> List[Candidate]:
    query = " ".join(terms[:6]) or "research"
    try:
        resp = get(ENDPOINT, params={"q": query}, timeout=25.0)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return []

    out: List[Candidate] = []
    for i, res in enumerate(soup.select(".result")[:max_results]):
        a = res.select_one(".result__a")
        if not a:
            continue
        url = _clean_ddg_url(a.get("href", ""))
        snippet_el = res.select_one(".result__snippet")
        out.append(Candidate(
            source_id=f"web:{i}:{abs(hash(url)) % 10_000_000}",
            title=a.get_text(strip=True),
            authors=[],
            year=None,
            venue="web",
            abstract=snippet_el.get_text(" ", strip=True) if snippet_el else "",
            identifier=url,
            url=url,
            source="web",
        ))
    return out
