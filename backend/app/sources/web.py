"""Web search for grey literature (lab blogs, technical reports). Read-only.
Uses the keyless DuckDuckGo HTML endpoint; degrades gracefully to [] if blocked.

Authors and publication year are recovered best-effort from each result page's
own bibliographic metadata (Highwire ``citation_*`` tags, JSON-LD, Dublin Core,
generic ``<meta name="author">``). This is deterministic and read-only — no model
is in the loop, so it adds NO hallucination surface: values are copied verbatim
from the page's metadata, never inferred. Pages with no usable metadata keep
``authors=[]`` / ``year=None`` and render title-first per APA 7."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote
from typing import List
from bs4 import BeautifulSoup
from ..schemas import Candidate
from ..config import config
from ._http import get

ENDPOINT = "https://html.duckduckgo.com/html/"


def _clean_ddg_url(href: str) -> str:
    m = re.search(r"uddg=([^&]+)", href)
    return unquote(m.group(1)) if m else href


# ── Author recovery from a result page's bibliographic metadata ──────────────
# Strings that betray a publisher/site rather than a person — rejected outright.
_BAD_AUTHOR = re.compile(r"https?://|@|\d{3,}|\b(?:inc|llc|ltd|press|news|staff|editor|admin)\b", re.I)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _clean_authors(names: List[str]) -> List[str]:
    """Keep only plausible person names: 2+ tokens, no publisher/URL markers,
    deduped, capped. Precision over recall — a wrong author is worse than none."""
    out: List[str] = []
    seen: set[str] = set()
    for raw in names:
        n = re.sub(r"\s+", " ", (raw or "").strip()).strip(",;")
        # Highwire / Dublin Core tags use "Surname, Given" order; the rest of the
        # pipeline (and the APA renderer's last-token-is-surname rule) expects
        # "Given Surname" — flip on the first comma so names render correctly.
        if "," in n:
            last, _, first = n.partition(",")
            if last.strip() and first.strip():
                n = f"{first.strip()} {last.strip()}"
        if not n or len(n) > 80 or len(n.split()) < 2 or _BAD_AUTHOR.search(n):
            continue
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
        if len(out) >= 25:
            break
    return out


def _iter_jsonld(soup: BeautifulSoup):
    """Yield every JSON-LD object on the page, walking lists and @graph."""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                graph = node.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
                yield node


def _authors_from_jsonld(soup: BeautifulSoup) -> List[str]:
    out: List[str] = []
    for node in _iter_jsonld(soup):
        author = node.get("author")
        if not author:
            continue
        for au in (author if isinstance(author, list) else [author]):
            if isinstance(au, str):
                out.append(au)
            elif isinstance(au, dict) and isinstance(au.get("name"), str):
                out.append(au["name"])
    return out


def _meta_contents(soup: BeautifulSoup, attr: str, name: str) -> List[str]:
    return [m.get("content", "") for m in
            soup.find_all("meta", attrs={attr: re.compile(rf"^{name}$", re.I)})
            if m.get("content")]


def _authors_from_soup(soup: BeautifulSoup) -> List[str]:
    """Extract authors in descending order of reliability; first hit wins."""
    # 1. Highwire / Google Scholar tags — one tag per author, most reliable.
    hw = _meta_contents(soup, "name", "citation_author")
    if hw:
        return hw
    # 1b. citation_authors variant: a single ';'-separated tag.
    ca = _meta_contents(soup, "name", "citation_authors")
    if ca:
        return re.split(r"\s*;\s*", ca[0])
    # 2. JSON-LD author(s).
    jl = _authors_from_jsonld(soup)
    if jl:
        return jl
    # 3. Dublin Core creators.
    dc = _meta_contents(soup, "name", r"dc\.creator")
    if dc:
        return dc
    # 4. Generic / OpenGraph author meta (least reliable; often a site name).
    return _meta_contents(soup, "name", "author") + \
        _meta_contents(soup, "property", "article:author")


_YEAR_RE = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def _extract_year(s: str) -> int | None:
    m = _YEAR_RE.search(s or "")
    return int(m.group(1)) if m else None


def _year_from_soup(soup: BeautifulSoup) -> int | None:
    """Recover a publication year from reliable date metadata, in priority order.
    Bare/last-modified dates are deliberately excluded to avoid wrong years."""
    sources = [
        ("name", "citation_publication_date"),
        ("name", "citation_date"),
        ("name", "citation_year"),
        ("property", "article:published_time"),
        ("name", r"dc\.date"),
    ]
    for attr, name in sources:
        for content in _meta_contents(soup, attr, name):
            y = _extract_year(content)
            if y:
                return y
    for node in _iter_jsonld(soup):
        for key in ("datePublished", "dateCreated"):
            y = _extract_year(str(node.get(key) or ""))
            if y:
                return y
    return None


def _page_title(soup: BeautifulSoup) -> str:
    for attr, name in [("name", "citation_title"), ("property", "og:title")]:
        hit = _meta_contents(soup, attr, name)
        if hit:
            return hit[0]
    if soup.title and soup.title.string:
        return soup.title.string
    return ""


def _title_match(page_title: str, serp_title: str) -> bool:
    """Guard against redirects/wrong pages: the page's own title should overlap
    the search-result title. If either is unknown, don't block (return True)."""
    a, b = _norm(page_title), _norm(serp_title)
    if not a or not b:
        return True
    return a in b or b in a or a[:24] == b[:24]


def _enrich(cand: Candidate) -> Candidate:
    """Best-effort: fetch the page and copy its own author metadata onto the
    candidate. Never raises; on any failure the candidate is returned unchanged."""
    if not config.WEB_ENRICH or not cand.url:
        return cand
    try:
        resp = get(cand.url, timeout=config.WEB_ENRICH_TIMEOUT)
        if resp.status_code != 200 or "html" not in resp.headers.get("content-type", "").lower():
            return cand
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return cand
    if not _title_match(_page_title(soup), cand.title):
        return cand
    authors = _clean_authors(_authors_from_soup(soup))
    if authors:
        cand.authors = authors
    if cand.year is None:
        year = _year_from_soup(soup)
        if year:
            cand.year = year
    return cand


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

    # Recover authors from each result page's metadata, in parallel and bounded
    # by a tight timeout so a slow/blocking page can't stall the search stage.
    if config.WEB_ENRICH and out:
        with ThreadPoolExecutor(max_workers=min(8, len(out))) as ex:
            out = list(ex.map(_enrich, out))
    return out
