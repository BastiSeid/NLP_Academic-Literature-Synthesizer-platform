"""Regression test: "no sources → no fabricated review" short-circuit.

Guards the behavior added in ``app/pipeline/orchestrator.py`` (``_finalize_no_sources``
plus the three guards in ``_run_after_gate``): when search finds no candidates, when none
survive screening, or when extract grounds zero notes, the pipeline must stop *before* the
Synthesizer, emit a short "Literature review not generated" message (never a fabricated
paper-formatted review), leave ``st.synth`` as ``None``, mark downstream stages "skipped",
and finish with status ``done``.

This is a NO-COST test: every stage that would call a paid agent is replaced with a stub,
``db.save_run`` is a no-op, and exports are redirected to a throwaway tempdir — nothing
touches the network, the Claude CLI, or the real SQLite/exports.

Run it either way:

    # standalone, no pytest needed (uses the venv interpreter):
    .venv/bin/python tests/test_no_sources_short_circuit.py

    # or under pytest, if installed:
    pytest tests/test_no_sources_short_circuit.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Make ``app`` importable whether this runs under pytest or directly as a script.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app import config as config_mod          # noqa: E402
from app import db as db_mod                  # noqa: E402
from app.pipeline import stages               # noqa: E402
from app.pipeline.orchestrator import manager  # noqa: E402
from app.schemas import Candidate, RunParams  # noqa: E402


def _one_candidate(st):
    st.candidates = [Candidate(source_id="c1", title="A candidate paper")]


def _keep_candidate(st):
    st.kept_ids = ["c1"]


# ── stubbed-pipeline harness ─────────────────────────────────────────────────
@contextmanager
def _stubbed_pipeline(search_fx=None, screen_fx=None, extract_fx=None):
    """Swap every paid stage + ``db.save_run`` for stubs and redirect exports to a
    tempdir, then run ``_run_after_gate`` against the given side-effect callables.

    ``search_fx``/``screen_fx``/``extract_fx`` receive the live ``state`` and mutate it
    to set up the scenario (e.g. add candidates, keep ids). Synthesize/verify are stubbed
    to count calls and return harmlessly — the whole point is to prove synthesize never
    runs on a no-sources path. Yields ``(state, calls)``."""
    calls = {k: 0 for k in ("search", "screen", "extract", "synthesize", "verify")}

    def _stage(name, fx):
        def stub(ctx, save, *args, **kwargs):
            calls[name] += 1
            if fx is not None:
                fx(ctx.state)
        return stub

    saved = {n: getattr(stages, f"stage_{n}") for n in calls}
    orig_save = db_mod.save_run
    orig_export = config_mod.config.EXPORT_DIR
    tmp = tempfile.mkdtemp(prefix="litsynth-nosrc-test-")
    state = None
    try:
        stages.stage_search = _stage("search", search_fx)
        stages.stage_screen = _stage("screen", screen_fx)
        stages.stage_extract = _stage("extract", extract_fx)
        stages.stage_synthesize = _stage("synthesize", None)
        stages.stage_verify = _stage("verify", None)
        db_mod.save_run = lambda *a, **k: None          # no SQLite writes
        config_mod.config.EXPORT_DIR = tmp              # exports land in the tempdir

        params = RunParams(export_dir=tmp)
        state = manager.create_run("regression: no-sources short-circuit", params)
        ctx = manager._runs[state.id]
        state.approved = True
        manager._run_after_gate(ctx)                    # auto-approved heavy phase
        yield state, calls
    finally:
        for n, fn in saved.items():
            setattr(stages, f"stage_{n}", fn)
        db_mod.save_run = orig_save
        config_mod.config.EXPORT_DIR = orig_export
        if state is not None:
            manager._runs.pop(state.id, None)
        shutil.rmtree(tmp, ignore_errors=True)


def _assert_no_fabricated_review(state, calls):
    """Shared assertions for every no-sources scenario."""
    # The Synthesizer must never run — that is what avoids the fabricated review and cost.
    assert calls["synthesize"] == 0, "Synthesizer was invoked on a no-sources run"
    # The run still finishes cleanly.
    assert state.status == "done", f"expected status 'done', got {state.status!r}"
    # No synthesis object → citation invariants (A1/A3) have nothing to trip on.
    assert state.synth is None, "st.synth should stay None when there are no sources"
    # The plain "not generated" message, not a paper.
    review = state.outputs.review_markdown
    assert "not generated" in review, "review should state it was not generated"
    assert "##" not in review, "review must not contain paper-section (##) headers"
    # Downstream stages that never ran are marked skipped (not left pending/running).
    assert state.stage("synthesize").status == "skipped"
    assert state.stage("verify").status == "skipped"


# ── scenarios: one per guard ─────────────────────────────────────────────────
def test_no_candidates_short_circuits():
    """Search finds nothing → short-circuit before screen/extract/synthesize."""
    with _stubbed_pipeline() as (state, calls):  # search leaves candidates empty
        _assert_no_fabricated_review(state, calls)
        assert calls["screen"] == 0, "screening should not run with zero candidates"
        assert calls["extract"] == 0, "extraction should not run with zero candidates"


def test_none_pass_screening_short_circuits():
    """Candidates exist but none survive screening → short-circuit before extract."""
    with _stubbed_pipeline(search_fx=_one_candidate) as (state, calls):  # screen keeps nothing
        _assert_no_fabricated_review(state, calls)
        assert calls["screen"] == 1, "screening should have run"
        assert calls["extract"] == 0, "extraction should not run when nothing is kept"


def test_zero_notes_short_circuits():
    """Sources kept but extract grounds zero notes → short-circuit before synthesize."""
    with _stubbed_pipeline(search_fx=_one_candidate,
                           screen_fx=_keep_candidate) as (state, calls):  # extract grounds nothing
        _assert_no_fabricated_review(state, calls)
        assert calls["extract"] == 1, "extraction should have run"


# ── standalone runner (no pytest required) ───────────────────────────────────
def _main() -> int:
    tests = [
        test_no_candidates_short_circuits,
        test_none_pass_screening_short_circuits,
        test_zero_notes_short_circuits,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failures += 1
            print(f"  ❌ {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ❌ {t.__name__}: unexpected {type(e).__name__}: {e}")
        else:
            print(f"  ✅ {t.__name__}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
