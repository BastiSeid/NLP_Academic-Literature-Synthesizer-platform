"""OpenAlex API. Free, read-only. Broad, interdisciplinary coverage."""
from __future__ import annotations

from typing import List
from ..schemas import Candidate
from ..config import config
from ._http import get

API = "https://api.openalex.org/works"


def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    positions = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def search(terms: List[str], max_results: int = 25) -> List[Candidate]:
    query = " ".join(terms[:6]) or "research"
    params = {"search": query, "per_page": min(max_results, 50)}
    if config.OPENALEX_EMAIL:
        params["mailto"] = config.OPENALEX_EMAIL
    try:
        resp = get(API, params=params, timeout=30.0)
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", []) or []
    except Exception:
        return []

    out: List[Candidate] = []
    for w in results:
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        authors = [a.get("author", {}).get("display_name", "")
                   for a in (w.get("authorships") or [])]
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
        out.append(Candidate(
            source_id=f"openalex:{(w.get('id') or '').split('/')[-1]}",
            title=(w.get("title") or "").strip(),
            authors=authors,
            year=w.get("publication_year"),
            venue=venue,
            abstract=_reconstruct_abstract(w.get("abstract_inverted_index")),
            identifier=doi or (w.get("id") or ""),
            url=w.get("id") or (("https://doi.org/" + doi) if doi else ""),
            source="openalex",
            score=w.get("cited_by_count"),
        ))
    return out
