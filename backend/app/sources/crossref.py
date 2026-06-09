"""Crossref REST API. Free, read-only. The DOI backbone — ~150M works across
every discipline, the broadest single bibliographic source available with an
open API. Joining the 'polite pool' (mailto) gets faster, more reliable service."""
from __future__ import annotations

import re
from typing import List
from ..schemas import Candidate
from ..config import config
from ._http import get
from ._merge import by_term

API = "https://api.crossref.org/works"


def _strip_jats(abstract: str | None) -> str:
    """Crossref abstracts are JATS XML; strip tags down to plain text."""
    if not abstract:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", abstract)).strip()


def _year(item: dict) -> int | None:
    parts = ((item.get("issued") or {}).get("date-parts") or [[None]])
    try:
        return int(parts[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def _query_one(query: str, max_results: int) -> List[Candidate]:
    params = {"query": query, "rows": min(max_results, 100)}
    if config.OPENALEX_EMAIL:  # reused as a generic contact for the polite pool
        params["mailto"] = config.OPENALEX_EMAIL
    resp = get(API, params=params, timeout=30.0, retries=2, backoff=3.0)
    if resp.status_code != 200:
        return []
    items = (resp.json().get("message") or {}).get("items", []) or []

    out: List[Candidate] = []
    for it in items:
        doi = (it.get("DOI") or "").strip()
        title = (it.get("title") or [""])[0].strip()
        if not title:
            continue
        authors = [" ".join(p for p in (a.get("given"), a.get("family")) if p).strip()
                   for a in (it.get("author") or [])]
        venue = (it.get("container-title") or [None])[0]
        out.append(Candidate(
            source_id=f"crossref:{doi}",
            title=title,
            authors=[a for a in authors if a],
            year=_year(it),
            venue=venue,
            abstract=_strip_jats(it.get("abstract")),
            identifier=doi,
            url=it.get("URL") or (f"https://doi.org/{doi}" if doi else ""),
            source="crossref",
            score=it.get("is-referenced-by-count"),
        ))
    return out


def search(terms: List[str], max_results: int = 25) -> List[Candidate]:
    """Query each term separately and union the results."""
    return by_term(_query_one, terms, max_results)
