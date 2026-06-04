"""Output assembly: BibTeX, JSON citations, the markdown review, and file export.
Pure functions over the run state — no model calls here."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List
from .schemas import Candidate, CitationVerdict


def _cite_key(c: Candidate) -> str:
    first_author = (c.authors[0].split()[-1] if c.authors else "anon")
    first_author = re.sub(r"[^A-Za-z]", "", first_author) or "anon"
    year = c.year or "n.d."
    title_word = ""
    for w in re.sub(r"[^A-Za-z ]", "", c.title).split():
        if len(w) > 3:
            title_word = w.lower()
            break
    return f"{first_author.lower()}{year}{title_word}"


def _bibtex_type(c: Candidate) -> str:
    if c.source == "arxiv":
        return "misc"
    if c.venue and c.venue not in ("web", "arXiv"):
        return "article"
    return "misc"


def to_bibtex(kept: List[Candidate]) -> str:
    seen: dict[str, int] = {}
    entries = []
    for c in kept:
        key = _cite_key(c)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}{chr(ord('a') + seen[key] - 1)}"
        fields = []
        fields.append(f"  title = {{{c.title}}}")
        if c.authors:
            fields.append(f"  author = {{{' and '.join(c.authors)}}}")
        if c.year:
            fields.append(f"  year = {{{c.year}}}")
        if c.venue:
            fields.append(f"  journal = {{{c.venue}}}")
        if c.identifier.startswith("10."):
            fields.append(f"  doi = {{{c.identifier}}}")
        elif c.source == "arxiv":
            fields.append(f"  eprint = {{{c.identifier}}}")
            fields.append("  archivePrefix = {arXiv}")
        if c.url:
            fields.append(f"  url = {{{c.url}}}")
        fields.append(f"  note = {{source_id: {c.source_id}}}")
        entries.append(f"@{_bibtex_type(c)}{{{key},\n" + ",\n".join(fields) + "\n}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def to_citations_json(kept: List[Candidate], verdicts: List[CitationVerdict]) -> str:
    backed: dict[str, list] = {}
    for v in verdicts:
        if v.supported:
            backed.setdefault(v.source_id, []).append(v.claim)
    payload = []
    for c in kept:
        payload.append({
            "source_id": c.source_id,
            "title": c.title,
            "authors": c.authors,
            "year": c.year,
            "venue": c.venue,
            "identifier": c.identifier,
            "url": c.url,
            "source": c.source,
            "bibtex_key": _cite_key(c),
            "verified_claims": backed.get(c.source_id, []),
        })
    return json.dumps(payload, indent=2, ensure_ascii=False)


def write_exports(export_dir: str, run_id: str, *, review_md: str, mermaid: str,
                  bibtex: str, citations_json: str, rejection_md: str) -> List[str]:
    base = Path(export_dir) / run_id
    base.mkdir(parents=True, exist_ok=True)
    files = {
        "literature_review.md": review_md,
        "synthesis_diagram.mmd": mermaid,
        "citations.bib": bibtex,
        "citations.json": citations_json,
        "rejection_log.md": rejection_md,
    }
    written = []
    for name, content in files.items():
        path = base / name
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return written


def rejection_log_markdown(rejections) -> str:
    lines = ["# Rejection Log", "",
             "_The moat is what's rejected._", "",
             "| Source | Reason | Justification |", "|---|---|---|"]
    for r in rejections:
        title = (r.title or r.source_id).replace("|", "\\|")[:80]
        just = r.justification.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {title} | `{r.reason_code}` | {just} |")
    return "\n".join(lines) + "\n"
