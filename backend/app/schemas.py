"""Pydantic schemas — the contract every subagent output is validated against
before the next stage consumes it (output-shape validation invariant)."""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ── Run params (from the UI New Run screen) ──────────────────────────────────
class RunParams(BaseModel):
    date_range: Optional[str] = None            # e.g. "2018-2026" or null
    max_candidates: int = 80
    max_kept: int = 25
    source_set: List[str] = Field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex", "crossref", "web"]
    )
    export_dir: Optional[str] = None
    cost_cap_usd: Optional[float] = None        # overrides global default if set
    model: Optional[str] = None                 # per-run model override; None → server default


class NewRunRequest(BaseModel):
    query: str
    params: RunParams = Field(default_factory=RunParams)


# ── Stage 1: Scout scope plan ────────────────────────────────────────────────
class ScopePlan(BaseModel):
    sub_questions: List[str]
    search_terms: List[str]
    rationale: str = ""


# ── Stage 2: Scout candidates ────────────────────────────────────────────────
class Candidate(BaseModel):
    source_id: str                              # stable internal id
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: str = ""
    identifier: str = ""                         # DOI / arXiv id / URL
    url: str = ""
    source: str = ""                             # primary (surviving) source after dedupe
    score: Optional[float] = None
    merged_from: List[str] = Field(default_factory=list)  # all sources that found this paper


# ── Stage 3: Gatekeeper output ───────────────────────────────────────────────
class RejectionEntry(BaseModel):
    source_id: str
    title: str
    reason_code: str                            # e.g. OFF_TOPIC, LOW_QUALITY, DUPLICATE, OUTDATED
    justification: str


class ScreenResult(BaseModel):
    kept_ids: List[str]
    rejections: List[RejectionEntry]


# ── Stage 3b: Arbiter (reconciles dual-screener disagreements) ───────────────
class ArbiterDecision(BaseModel):
    source_id: str
    decision: Literal["keep", "reject"]
    reason: str = ""                            # why the arbiter sided this way


class ArbiterOutput(BaseModel):
    decisions: List[ArbiterDecision]


# ── Stage 4: Reader notes ────────────────────────────────────────────────────
class ReaderNote(BaseModel):
    source_id: str
    claim: str
    evidence: str
    location: str                               # section / page / "abstract"
    quote: str = ""                             # verbatim sentence the claim rests on
    note_type: Literal["claim", "method", "finding"] = "finding"


class ReaderOutput(BaseModel):
    source_id: str
    notes: List[ReaderNote]


# ── Stage 4b: Note grounding gate (verifies notes vs the paper's own text) ───
class NoteVerdict(BaseModel):
    source_id: str
    claim: str
    grounded: bool                              # True → traceable to this paper's text
    reason: str = ""


class NoteVerifyOutput(BaseModel):
    verdicts: List[NoteVerdict]


# ── Stage 5: Synthesizer output ──────────────────────────────────────────────
class CitationRef(BaseModel):
    marker: str                                 # inline marker, e.g. "S3"
    source_id: str
    claim: str                                  # the claim this citation backs


class SynthOutput(BaseModel):
    review_markdown: str
    mermaid: str
    citations: List[CitationRef]
    themes: List[str] = Field(default_factory=list)
