"""Per-term retrieval helper.

Query each search term SEPARATELY and union the results (deduped by source_id,
capped). Searching terms one at a time is what lets lenient relevance APIs
(OpenAlex, Crossref, Semantic Scholar, DuckDuckGo) actually match: concatenating
6 distinct phrases into one ~30-word bag-of-words query returns nothing on most
engines except for densely-covered (STEM) topics. arXiv is the exception — it
ORs its terms natively — so it does not use this helper.
"""
from __future__ import annotations

from typing import Callable, List
from ..schemas import Candidate

# A function that runs ONE query string against a source and returns candidates.
QueryOne = Callable[[str, int], List[Candidate]]


def by_term(query_one: QueryOne, terms: List[str], max_results: int,
            *, max_terms: int = 8) -> List[Candidate]:
    """Run `query_one(term, n)` for each term and union the results.

    - Dedupes within the source by `source_id` (cross-source dedupe still happens
      later in `dedupe.dedupe`).
    - Caps total at `max_results`, distributing the budget across terms.
    - A single failing term is collected, not fatal. Only if EVERY term errors
      and nothing came back is the last error re-raised, so the search stage can
      surface a genuine source outage instead of a silent zero.
    """
    picked = [t.strip() for t in (terms or []) if t and t.strip()][:max_terms] or ["research"]
    per_term = max(3, max_results // len(picked) + 2)
    seen: set[str] = set()
    out: List[Candidate] = []
    errors: List[Exception] = []
    for term in picked:
        try:
            results = query_one(term, per_term)
        except Exception as e:  # one bad term must not sink the rest
            errors.append(e)
            continue
        for c in results:
            if c.source_id in seen:
                continue
            seen.add(c.source_id)
            out.append(c)
    if not out and errors:
        raise errors[-1]
    return out[:max_results]
