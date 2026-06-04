"""arXiv API (Atom). Free, read-only. Where the latest CS/ML preprints live."""
from __future__ import annotations

import feedparser
from typing import List
from ..schemas import Candidate
from ._http import get

API = "http://export.arxiv.org/api/query"


def search(terms: List[str], max_results: int = 25) -> List[Candidate]:
    query = " OR ".join(f'all:"{t}"' for t in terms[:8]) or "all:research"
    try:
        resp = get(API, params={
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }, timeout=30.0, retries=3, backoff=3.0)
        feed = feedparser.parse(resp.text)
    except Exception:
        return []

    out: List[Candidate] = []
    for e in feed.entries:
        arxiv_id = e.get("id", "").split("/abs/")[-1]
        year = None
        if e.get("published"):
            try:
                year = int(e["published"][:4])
            except ValueError:
                year = None
        out.append(Candidate(
            source_id=f"arxiv:{arxiv_id}",
            title=e.get("title", "").replace("\n", " ").strip(),
            authors=[a.get("name", "") for a in e.get("authors", [])],
            year=year,
            venue="arXiv",
            abstract=e.get("summary", "").replace("\n", " ").strip(),
            identifier=arxiv_id,
            url=e.get("id", ""),
            source="arxiv",
        ))
    return out
