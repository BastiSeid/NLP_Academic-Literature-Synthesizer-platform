"""Orchestrator: owns a run end-to-end, routes work through the six stages,
enforces stop conditions and invariants, pauses at the approval gate, and
assembles + validates the four deliverables. Pure delegation + assembly — it
makes no external calls itself."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from ..config import config
from .. import db
from ..schemas import RunParams, ScopePlan, Candidate
from .. import exporters
from .state import RunState
from .guards import (
    RunContext, Cancelled, CostCapExceeded, WallClockExceeded, MaxStepsExceeded,
)
from . import stages


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunManager:
    def __init__(self) -> None:
        self._runs: Dict[str, RunContext] = {}

    # ── persistence ──────────────────────────────────────────────────────────
    def _save(self, ctx: RunContext) -> None:
        st = ctx.state
        st.updated_at = _now()
        db.save_run(st.id, st.query, st.status, _phase_of(st), st.cost_usd,
                    st.created_at, st.updated_at, st.model_dump_json())

    # ── lifecycle ────────────────────────────────────────────────────────────
    def create_run(self, query: str, params: RunParams) -> RunState:
        run_id = uuid.uuid4().hex[:12]
        now = _now()
        state = RunState(id=run_id, query=query, params=params,
                         status="created", created_at=now, updated_at=now)
        ctx = RunContext(state)
        self._runs[run_id] = ctx
        self._save(ctx)
        return state

    def get_state(self, run_id: str) -> Optional[RunState]:
        ctx = self._runs.get(run_id)
        if ctx:
            return ctx.state
        raw = db.load_state(run_id)
        if raw:
            return RunState.model_validate_json(raw)
        return None

    def cancel(self, run_id: str) -> bool:
        ctx = self._runs.get(run_id)
        if not ctx:
            return False
        ctx.cancel_event.set()
        return True

    async def resume(self, run_id: str) -> bool:
        """Resume a failed/interrupted run from its first not-done stage, reusing
        the checkpointed state (and accumulated cost). Returns False if the run is
        unknown or not in a resumable state."""
        ctx = self._runs.get(run_id)
        if ctx is None:
            raw = db.load_state(run_id)
            if not raw:
                return False
            ctx = RunContext(RunState.model_validate_json(raw))
            self._runs[run_id] = ctx
        st = ctx.state
        if st.status not in ("failed", "interrupted"):
            return False  # guard: only a stuck run can be resumed

        # fresh control handles; clear the prior failure marks
        ctx.cancel_event.clear()
        ctx.start_time = __import__("time").monotonic()
        st.error = ""
        for s in st.stages:
            if s.status == "failed":
                s.status = "pending"
                s.detail = ""

        if not _stage_done(st, "scope"):
            # scoping never completed → re-scope back to the approval gate
            st.status = "created"; self._save(ctx)
            asyncio.create_task(asyncio.to_thread(self._run_until_gate, ctx))
        elif st.approved:
            # approved → resume heavy phases; _run_after_gate skips done stages
            order = [("search", "searching"), ("screen", "screening"),
                     ("extract", "extracting"), ("synthesize", "synthesizing"),
                     ("verify", "verifying")]
            st.status = next((s for n, s in order if not _stage_done(st, n)), "assembling")
            self._save(ctx)
            asyncio.create_task(asyncio.to_thread(self._run_after_gate, ctx))
        else:
            # interrupted while waiting at the gate → restore the gate, don't auto-spend
            st.status = "awaiting_approval"; self._save(ctx)
        return True

    # ── gate: scoping then pause ─────────────────────────────────────────────
    async def start(self, run_id: str) -> None:
        ctx = self._runs[run_id]
        asyncio.create_task(asyncio.to_thread(self._run_until_gate, ctx))

    def _run_until_gate(self, ctx: RunContext) -> None:
        st = ctx.state
        try:
            st.status = "scoping"
            self._save(ctx)
            stages.stage_scope(ctx, self._save)
            st.status = "awaiting_approval"   # ← pipeline pauses here
            self._save(ctx)
        except Exception as e:  # noqa: BLE001
            self._fail(ctx, e, "scope")

    # ── gate actions ─────────────────────────────────────────────────────────
    def revise_plan(self, run_id: str, plan: ScopePlan, source_set) -> bool:
        ctx = self._runs.get(run_id)
        if not ctx or ctx.state.status != "awaiting_approval":
            return False
        ctx.state.scope_plan = plan
        if source_set:
            ctx.state.plan_source_set = list(source_set)
        ctx.state.stage("scope").detail = (
            f"revised: {len(plan.sub_questions)} sub-questions, {len(plan.search_terms)} terms"
        )
        self._save(ctx)
        return True

    async def approve(self, run_id: str) -> bool:
        ctx = self._runs.get(run_id)
        if not ctx or ctx.state.status != "awaiting_approval":
            return False
        ctx.state.approved = True
        ctx.start_time = __import__("time").monotonic()  # reset wall-clock for heavy phase
        asyncio.create_task(asyncio.to_thread(self._run_after_gate, ctx))
        return True

    # ── heavy phases after approval ──────────────────────────────────────────
    def _run_after_gate(self, ctx: RunContext) -> None:
        st = ctx.state
        try:
            if not _stage_done(st, "search"):
                st.status = "searching"; self._save(ctx)
                stages.stage_search(ctx, self._save)

            if not _stage_done(st, "screen"):
                st.status = "screening"; self._save(ctx)
                stages.stage_screen(ctx, self._save)

            if not _stage_done(st, "extract"):
                st.status = "extracting"; self._save(ctx)
                stages.stage_extract(ctx, self._save)

            if not _stage_done(st, "synthesize"):
                st.status = "synthesizing"; self._save(ctx)
                stages.stage_synthesize(ctx, self._save)

            if not _stage_done(st, "verify"):
                st.status = "verifying"; self._save(ctx)
                self._verify_loop(ctx)

            st.status = "assembling"; self._save(ctx)
            self._finalize(ctx)

            st.status = "done"; self._save(ctx)
        except (Cancelled,) as e:
            self._cancelled(ctx, e)
        except (CostCapExceeded, WallClockExceeded, MaxStepsExceeded) as e:
            self._fail(ctx, e, st.status, stop=True)
        except Exception as e:  # noqa: BLE001
            self._fail(ctx, e, st.status)

    def _verify_loop(self, ctx: RunContext) -> None:
        """Verifier → unsupported claims routed back to Reader/Synth, bounded."""
        st = ctx.state
        for rnd in range(config.MAX_VERIFY_ROUNDS + 1):
            out = stages.stage_verify(ctx, self._save)
            unsupported = [v for v in out.verdicts if not v.supported]
            if not unsupported or rnd >= config.MAX_VERIFY_ROUNDS:
                break
            st.verify_rounds = rnd + 1
            involved = sorted({v.source_id for v in unsupported})
            stages.stage_extract(ctx, self._save, only_ids=involved)  # ← back to EXTRACT
            feedback = "\n".join(
                f"- [{v.marker}] claim '{v.claim}' (source {v.source_id}) "
                f"unsupported: {v.reason}" for v in unsupported
            )
            stages.stage_synthesize(ctx, self._save, feedback=feedback)
        st.stage("verify").status = "done"
        self._save(ctx)

    def _finalize(self, ctx: RunContext) -> None:
        """Assemble + validate the four deliverables, enforce invariants in code."""
        st = ctx.state
        by_id = {c.source_id: c for c in st.candidates}
        kept_set = set(st.kept_ids)

        review = st.synth.review_markdown if st.synth else "# Literature Review\n\n(empty)"
        mermaid = st.synth.mermaid if st.synth else "graph TD\n  A[No synthesis produced]"

        # Invariant A3: never present an unverified claim as verified — mark them.
        supported = {v.marker for v in st.verdicts if v.supported}
        unsupported = {v.marker for v in st.verdicts if not v.supported} - supported
        for m in sorted(unsupported):
            review = review.replace(f"[{m}]", f"[{m} ⚠UNVERIFIED]")
        if unsupported:
            review += (
                "\n\n---\n\n> **⚠ Unverified claims:** the citation markers above tagged "
                "`⚠UNVERIFIED` could not be confirmed against their cited source after "
                f"{config.MAX_VERIFY_ROUNDS} verification rounds and should be read with caution.\n"
            )

        # Invariant A1: rejected sources never appear → cite only kept + verified-or-marked.
        kept_candidates = [by_id[sid] for sid in st.kept_ids if sid in by_id]

        # APA 7 reference list, appended AFTER marker-based verification tagging so the
        # inline [source_id] markers (which the verifier keys on) stay intact upstream.
        refs = exporters.apa_references_section(kept_candidates)
        if refs:
            review = review.rstrip() + "\n\n" + refs

        bibtex = exporters.to_bibtex(kept_candidates)
        citations_json = exporters.to_citations_json(kept_candidates, st.verdicts)
        rejection_md = exporters.rejection_log_markdown(st.rejections)

        st.outputs.review_markdown = review
        st.outputs.mermaid = mermaid
        st.outputs.bibtex = bibtex
        st.outputs.citations_json = citations_json
        st.outputs.rejection_log = st.rejections

        export_dir = st.params.export_dir or config.EXPORT_DIR
        try:
            st.outputs.export_paths = exporters.write_exports(
                export_dir, st.id, review_md=review, mermaid=mermaid,
                bibtex=bibtex, citations_json=citations_json, rejection_md=rejection_md,
            )
        except Exception:
            st.outputs.export_paths = []
        self._save(ctx)

    # ── failure handling ─────────────────────────────────────────────────────
    def _running_stage(self, st: RunState):
        for s in st.stages:
            if s.status == "running":
                return s
        return None

    def _fail(self, ctx: RunContext, err: Exception, phase: str, stop: bool = False) -> None:
        st = ctx.state
        st.error = f"{type(err).__name__}: {err}"
        s = self._running_stage(st)
        if s:
            s.status = "failed"
            s.detail = st.error[:120]
        st.status = "failed"
        self._save(ctx)

    def _cancelled(self, ctx: RunContext, err: Exception) -> None:
        st = ctx.state
        st.error = "cancelled by user (kill switch)"
        s = self._running_stage(st)
        if s:
            s.status = "skipped"
            s.detail = "cancelled"
        st.status = "cancelled"
        self._save(ctx)


def _stage_done(st: RunState, name: str) -> bool:
    try:
        return st.stage(name).status == "done"
    except KeyError:
        return False


def _phase_of(st: RunState) -> str:
    return st.status


manager = RunManager()
