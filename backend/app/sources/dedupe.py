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
    contributors: dict[str, list[str]] = {}
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
        # Track every source that found this paper, even if its copy was merged
        # away — otherwise dedupe makes it look like only the winning source
        # (usually OpenAlex, which has the richest abstracts) ever contributed.
        if c.source and c.source not in contributors.setdefault(key, []):
            contributors[key].append(c.source)
    out: List[Candidate] = []
    for k in order:
        c = by_key[k]
        c.merged_from = contributors[k]
        out.append(c)
    return out
