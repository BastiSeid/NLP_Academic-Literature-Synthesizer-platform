"""Semantic Scholar Graph API. Free, read-only. Citation graph → seminal + new work."""
from __future__ import annotations

from typing import List
from ..schemas import Candidate
from ..config import config
from ._http import get
from ._merge import by_term

API = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,authors,year,venue,abstract,externalIds,url,citationCount"


def _query_one(query: str, max_results: int) -> List[Candidate]:
    headers = {}
    if config.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY
    resp = get(API, params={"query": query, "limit": min(max_results, 100),
                            "fields": FIELDS}, headers=headers, timeout=30.0,
               retries=2, backoff=3.0)
    # Surface rate-limiting (the common failure mode without an API key) so the
    # search stage reports it instead of it looking like "no results".
    if resp.status_code == 429:
        raise RuntimeError("Semantic Scholar rate-limited (set SEMANTIC_SCHOLAR_API_KEY)")
    if resp.status_code != 200:
        return []
    data = resp.json().get("data", []) or []

    out: List[Candidate] = []
    for p in data:
        ext = p.get("externalIds") or {}
        ident = ext.get("DOI") or ext.get("ArXiv") or p.get("paperId", "")
        out.append(Candidate(
            source_id=f"s2:{p.get('paperId','')}",
            title=(p.get("title") or "").strip(),
            authors=[a.get("name", "") for a in (p.get("authors") or [])],
            year=p.get("year"),
            venue=p.get("venue") or None,
            abstract=(p.get("abstract") or "").strip(),
            identifier=ident,
            url=p.get("url") or "",
            source="semantic_scholar",
            score=p.get("citationCount"),
        ))
    return out


def search(terms: List[str], max_results: int = 25) -> List[Candidate]:
    """Query each term separately and union the results."""
    return by_term(_query_one, terms, max_results)
