"""Deterministic, network-free tests for the web grey-literature author
recovery (sources/web.py). Exercises each metadata source and the guards."""
from bs4 import BeautifulSoup

from app.sources import web


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_highwire_citation_author_tags():
    html = """
    <meta name="citation_author" content="Jane Q. Doe">
    <meta name="citation_author" content="John Smith">
    """
    assert web._authors_from_soup(_soup(html)) == ["Jane Q. Doe", "John Smith"]


def test_citation_authors_semicolon_variant():
    html = '<meta name="citation_authors" content="Jane Doe; John Smith">'
    assert web._authors_from_soup(_soup(html)) == ["Jane Doe", "John Smith"]


def test_jsonld_author_list_of_persons():
    html = """
    <script type="application/ld+json">
    {"@type": "Article",
     "author": [{"@type": "Person", "name": "Ada Lovelace"},
                {"@type": "Person", "name": "Alan Turing"}]}
    </script>"""
    assert web._authors_from_soup(_soup(html)) == ["Ada Lovelace", "Alan Turing"]


def test_jsonld_graph_and_string_author():
    html = """
    <script type="application/ld+json">
    {"@graph": [{"@type": "WebPage", "author": "Grace Hopper"}]}
    </script>"""
    assert web._authors_from_soup(_soup(html)) == ["Grace Hopper"]


def test_generic_meta_author_fallback():
    html = '<meta name="author" content="Margaret Hamilton">'
    assert web._authors_from_soup(_soup(html)) == ["Margaret Hamilton"]


def test_clean_authors_flips_surname_comma_given_order():
    # Highwire citation_author form → "Given Surname" for the APA renderer.
    assert web._clean_authors(["Gao, Yunfan", "Smith, John A."]) == \
        ["Yunfan Gao", "John A. Smith"]


def test_clean_authors_rejects_orgs_and_urls():
    raw = ["OpenAI", "Acme Inc", "https://example.com", "Editorial Staff",
           "Katherine Johnson", "Katherine Johnson"]  # dup at the end
    assert web._clean_authors(raw) == ["Katherine Johnson"]


def test_title_match_allows_site_suffix_and_blocks_mismatch():
    assert web._title_match("Retrieval-Augmented Generation",
                            "Retrieval-Augmented Generation - Wikipedia")
    assert not web._title_match("Completely Different Page", "RAG Survey 2024")
    assert web._title_match("", "anything")  # unknown → don't block


def test_no_metadata_returns_empty():
    assert web._clean_authors(web._authors_from_soup(_soup("<p>hello</p>"))) == []


def test_year_from_citation_meta():
    html = '<meta name="citation_publication_date" content="2023/12/01">'
    assert web._year_from_soup(_soup(html)) == 2023


def test_year_from_jsonld_datepublished():
    html = ('<script type="application/ld+json">'
            '{"@type":"Article","datePublished":"2024-05-10T08:00:00Z"}</script>')
    assert web._year_from_soup(_soup(html)) == 2024


def test_year_from_article_published_time():
    html = '<meta property="article:published_time" content="2021-03-09">'
    assert web._year_from_soup(_soup(html)) == 2021


def test_extract_year_ignores_non_years():
    assert web._extract_year("updated 12 hours ago") is None
    assert web._extract_year("") is None


def test_year_absent_returns_none():
    assert web._year_from_soup(_soup("<p>no dates here</p>")) is None
