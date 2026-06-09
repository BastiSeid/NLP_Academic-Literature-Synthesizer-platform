"""Output assembly: BibTeX, JSON citations, the markdown review, and file export.
Pure functions over the run state — no model calls here."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List
from .schemas import Candidate


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


# ── APA 7th-edition rendering ────────────────────────────────────────────────
def _apa_author(name: str) -> str:
    """One author name → APA reference form 'Surname, F. M.'.
    Falls back to the raw token when a name can't be split (single token)."""
    parts = name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    surname = parts[-1]
    initials = " ".join(f"{p[0].upper()}." for p in parts[:-1] if p)
    return f"{surname}, {initials}".strip()


def _apa_authors(authors: List[str]) -> str:
    """Join an author list per APA 7 rules: '&' before the final author,
    and the 21+ rule (first 19, ellipsis, final author)."""
    names = [_apa_author(a) for a in authors if a and a.strip()]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    # 21+ authors: list the first 19, an ellipsis, then the final author (no '&')
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def _apa_surname_key(c: Candidate) -> str:
    """Sort key for the reference list: first author's surname, else title."""
    if c.authors and c.authors[0].strip():
        return c.authors[0].strip().split()[-1].lower()
    return (c.title or "").lower()


def apa_reference(c: Candidate) -> str:
    """A single APA 7 reference-list entry. Three shapes: journal article,
    arXiv preprint, and web/grey literature. Italics use Markdown asterisks."""
    year = c.year or "n.d."
    authors = _apa_authors(c.authors)
    title = (c.title or "").strip().rstrip(".")

    # arXiv preprint
    if c.source == "arxiv":
        head = f"{authors} ({year}). " if authors else ""
        url = c.url or (f"https://arxiv.org/abs/{c.identifier}" if c.identifier else "")
        eprint = f" (arXiv:{c.identifier})" if c.identifier else ""
        tail = f" {url}" if url else ""
        return f"{head}*{title}*{eprint}. arXiv.{tail}".strip()

    # Web / grey literature (often author-less → title takes the author slot)
    if c.source == "web" or (not c.identifier.startswith("10.") and not c.venue):
        if authors:
            head = f"{authors} ({year}). *{title}*."
        else:
            head = f"*{title}*. ({year})."
        tail = f" {c.url}" if c.url else ""
        return f"{head}{tail}".strip()

    # Journal article / DOI-bearing work
    head = f"{authors} ({year}). " if authors else f"*{title}*. ({year}). "
    body = f"{title}. " if authors else ""
    venue = f"*{c.venue}*. " if c.venue else ""
    if c.identifier.startswith("10."):
        link = f"https://doi.org/{c.identifier}"
    else:
        link = c.url or ""
    return f"{head}{body}{venue}{link}".strip().rstrip(".") + ("" if link else ".")


def _ref_keys(c: Candidate) -> set[str]:
    """The set of identity keys a paper can be matched on. DOI and normalized
    title are BOTH emitted when present, because the same paper can survive
    candidate-dedupe as two source_ids — a DOI-bearing copy and a title-only copy
    (sources/dedupe.py keys by DOI-or-title, so those keys never meet). Matching
    on either key lets the reference list still collapse them into one entry."""
    keys: set[str] = set()
    ident = (c.identifier or "").lower().replace("https://doi.org/", "").strip()
    if ident.startswith("10."):
        keys.add(f"doi:{ident}")
    norm = re.sub(r"[^a-z0-9]", "", (c.title or "").lower())
    if norm:
        keys.add(f"title:{norm}")
    if not keys:
        keys.add(f"sid:{c.source_id}")
    return keys


def _richer(a: Candidate, b: Candidate) -> Candidate:
    """The copy that renders the more complete APA entry: prefer DOI-bearing,
    then more authors."""
    rank = lambda c: (c.identifier.startswith("10."), len(c.authors))
    return b if rank(b) > rank(a) else a


def _dedupe_for_references(kept: List[Candidate]) -> List[Candidate]:
    """One Candidate per real paper. Papers are grouped by a UNION of their
    identity keys (DOI or normalized title), so a DOI-keyed copy and a title-keyed
    copy of the same paper merge; the richer copy represents the group."""
    groups: list[dict] = []
    for c in kept:
        keys = _ref_keys(c)
        matched = [g for g in groups if g["keys"] & keys]
        if not matched:
            groups.append({"keys": set(keys), "best": c})
            continue
        head = matched[0]
        for other in matched[1:]:          # candidate bridges two groups → merge them
            head["keys"] |= other["keys"]
            head["best"] = _richer(head["best"], other["best"])
            groups.remove(other)
        head["keys"] |= keys
        head["best"] = _richer(head["best"], c)
    return [g["best"] for g in groups]


def apa_references_section(kept: List[Candidate]) -> str:
    """The '## References' block: each source once, sorted alphabetically (APA)."""
    if not kept:
        return ""
    entries = sorted(_dedupe_for_references(kept), key=_apa_surname_key)
    lines = ["## References", ""]
    lines += [f"- {apa_reference(c)}" for c in entries]
    return "\n".join(lines) + "\n"


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


def to_citations_json(kept: List[Candidate]) -> str:
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
            "apa": apa_reference(c),
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
