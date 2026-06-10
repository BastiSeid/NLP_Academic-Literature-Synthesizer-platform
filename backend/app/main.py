"""FastAPI surface for the Academic Literature Synthesizer."""
from __future__ import annotations

from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import db
from .config import config
from .schemas import NewRunRequest, ScopePlan
from .pipeline.orchestrator import manager

app = FastAPI(title="Academic Literature Synthesizer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    db.mark_interrupted_runs()


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": config.MODEL,
        "models": config.AVAILABLE_MODELS,
        "cost_cap_usd": config.COST_CAP_USD,
    }


@app.post("/api/runs")
async def create_run(req: NewRunRequest):
    if not req.query.strip():
        raise HTTPException(400, "query is required")
    state = manager.create_run(req.query.strip(), req.params)
    await manager.start(state.id)
    return manager.get_state(state.id)


@app.get("/api/runs")
def list_runs():
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    state = manager.get_state(run_id)
    if not state:
        raise HTTPException(404, "run not found")
    return state


class ReviseBody(BaseModel):
    sub_questions: List[str]
    search_terms: List[str]
    rationale: str = ""
    source_set: Optional[List[str]] = None


@app.post("/api/runs/{run_id}/revise")
def revise_run(run_id: str, body: ReviseBody):
    plan = ScopePlan(sub_questions=body.sub_questions,
                     search_terms=body.search_terms, rationale=body.rationale)
    if not manager.revise_plan(run_id, plan, body.source_set):
        raise HTTPException(409, "run is not awaiting approval")
    return manager.get_state(run_id)


@app.post("/api/runs/{run_id}/approve")
async def approve_run(run_id: str):
    if not await manager.approve(run_id):
        raise HTTPException(409, "run is not awaiting approval")
    return manager.get_state(run_id)


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    if not manager.cancel(run_id):
        raise HTTPException(404, "run not active")
    return {"cancelled": True}


@app.post("/api/runs/{run_id}/resume")
async def resume_run(run_id: str):
    if not manager.get_state(run_id):
        raise HTTPException(404, "run not found")
    if not await manager.resume(run_id):
        raise HTTPException(409, "run is not resumable (must be failed or interrupted)")
    return manager.get_state(run_id)


_EXPORTS = {
    "review": ("review_markdown", "text/markdown"),
    "mermaid": ("mermaid", "text/plain"),
    "bibtex": ("bibtex", "text/plain"),
    "citations": ("citations_json", "application/json"),
}


@app.get("/api/runs/{run_id}/export/{kind}")
def export(run_id: str, kind: str):
    state = manager.get_state(run_id)
    if not state:
        raise HTTPException(404, "run not found")
    if kind not in _EXPORTS:
        raise HTTPException(400, "unknown export kind")
    attr, media = _EXPORTS[kind]
    return PlainTextResponse(getattr(state.outputs, attr) or "", media_type=media)
