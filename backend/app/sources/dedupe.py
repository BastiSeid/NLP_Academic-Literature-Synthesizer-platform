"""Cross-source candidate dedupe — merge duplicates by DOI then by normalized title."""
from __future__ import annotations

import re
from typing import List
from ..schemas import Candidate


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def _norm_doi(c: Candidate) -> str | None:
    ident = (c.identifier or "").lower().replace("https://doi.org/", "").strip()
    return ident if ident.startswith("10.") else None


def dedupe(cands: List[Candidate]) -> List[Candidate]:
    by_key: dict[str, Candidate] = {}
    order: List[str] = []
    for c in cands:
        key = _norm_doi(c) or _norm_title(c.title)
        if not key:
            key = c.source_id
        if key in by_key:
            # keep the richer record (longer abstract), prefer non-web source
            existing = by_key[key]
            better = c if (len(c.abstract) > len(existing.abstract)
                           and c.source != "web") else existing
            by_key[key] = better
        else:
            by_key[key] = c
            order.append(key)
    return [by_key[k] for k in order]
