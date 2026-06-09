"""Serializable run state — the single source of truth for a run, checkpointed
to SQLite after every stage so progress and results survive a page reload."""
from __future__ import annotations

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, model_validator

from ..schemas import (
    RunParams, Candidate, ScopePlan, RejectionEntry, ReaderNote,
    SynthOutput,
)

# UI pipeline stages (the five from the architecture flow)
STAGE_NAMES = ["scope", "search", "screen", "extract", "synthesize"]
StageState = Literal["pending", "running", "done", "failed", "skipped"]

RunStatus = Literal[
    "created", "scoping", "awaiting_approval", "searching", "screening",
    "extracting", "synthesizing", "assembling",
    "done", "failed", "cancelled", "interrupted",
]


class Stage(BaseModel):
    name: str
    status: StageState = "pending"
    detail: str = ""


class Counts(BaseModel):
    candidates: int = 0
    kept: int = 0
    rejected: int = 0
    notes_grounded: int = 0          # Stage 4 notes that passed the grounding gate
    notes_dropped: int = 0           # Stage 4 notes dropped as ungrounded

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_counts(cls, data):
        """Read-time compat shim: older persisted runs stored the grounding tally
        under `verified`/`unsupported`. Map them onto the current field names when
        the new fields are absent, so legacy runs still surface the metric. No-ops
        for current runs and never mutates the stored JSON."""
        if isinstance(data, dict):
            if "notes_grounded" not in data and "verified" in data:
                data = {**data, "notes_grounded": data["verified"]}
            if "notes_dropped" not in data and "unsupported" in data:
                data = {**data, "notes_dropped": data["unsupported"]}
        return data


class ScreenAgreement(BaseModel):
    """Inter-screener agreement signal from the dual-screening stage (Stage 3)."""
    agree_keep: int = 0              # both screeners kept
    agree_reject: int = 0            # both screeners rejected
    disagree: int = 0               # screeners differed → sent to the arbiter
    arbiter_keep: int = 0            # arbiter resolved a dispute as keep
    arbiter_reject: int = 0         # arbiter resolved a dispute as reject


class Outputs(BaseModel):
    review_markdown: str = ""
    mermaid: str = ""
    bibtex: str = ""
    citations_json: str = ""
    rejection_log: List[RejectionEntry] = Field(default_factory=list)
    export_paths: List[str] = Field(default_factory=list)


class RunState(BaseModel):
    id: str
    query: str
    params: RunParams
    status: RunStatus = "created"
    created_at: str
    updated_at: str

    stages: List[Stage] = Field(
        default_factory=lambda: [Stage(name=n) for n in STAGE_NAMES]
    )
    counts: Counts = Field(default_factory=Counts)

    scope_plan: Optional[ScopePlan] = None
    plan_source_set: List[str] = Field(default_factory=list)
    approved: bool = False

    candidates: List[Candidate] = Field(default_factory=list)
    kept_ids: List[str] = Field(default_factory=list)
    rejections: List[RejectionEntry] = Field(default_factory=list)
    screen_agreement: ScreenAgreement = Field(default_factory=ScreenAgreement)
    notes: Dict[str, List[ReaderNote]] = Field(default_factory=dict)
    dropped_notes: Dict[str, List[ReaderNote]] = Field(default_factory=dict)
    synth: Optional[SynthOutput] = None

    outputs: Outputs = Field(default_factory=Outputs)

    # accounting / guardrails
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    steps: int = 0
    error: str = ""

    def stage(self, name: str) -> Stage:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(name)
