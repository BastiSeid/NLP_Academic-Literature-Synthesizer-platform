"""Regression test: the Stage-4 note-grounding gate fails CLOSED.

Guards ``app/pipeline/stages.py::_verify_notes``. This gate is the platform's only
anti-hallucination layer (the Stage-6 citation verifier was removed), so when the
NOTE_VERIFIER returns a verdict count that does not match the note count, any note
whose verdict cannot be matched by claim text must be DROPPED — never silently kept.
Previously an empty or partial verdict list defaulted unmatched notes to grounded=True,
passing all notes unverified.

This is a NO-COST test: ``_charged_structured`` (the only model call) is replaced with
a stub returning a canned ``NoteVerifyOutput`` — nothing touches the network or the
Claude CLI.

Run it either way:

    # standalone, no pytest needed (uses the venv interpreter):
    .venv/bin/python tests/test_note_verify_fail_closed.py

    # or under pytest, if installed:
    pytest tests/test_note_verify_fail_closed.py
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

# Make ``app`` importable whether this runs under pytest or directly as a script.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.pipeline import stages                                      # noqa: E402
from app.schemas import Candidate, NoteVerdict, NoteVerifyOutput, ReaderNote  # noqa: E402

_CAND = Candidate(source_id="c1", title="A candidate paper")


def _notes(*claims: str) -> list[ReaderNote]:
    return [ReaderNote(source_id="c1", claim=c, evidence="ev", location="abstract")
            for c in claims]


@contextmanager
def _verifier_returns(verdicts: list[NoteVerdict]):
    """Stub the (only) model call so ``_verify_notes`` sees a canned verdict list."""
    orig = stages._charged_structured
    try:
        stages._charged_structured = lambda *a, **k: NoteVerifyOutput(verdicts=verdicts)
        yield
    finally:
        stages._charged_structured = orig


# ── scenarios ────────────────────────────────────────────────────────────────
def test_empty_verdicts_drops_all_notes():
    """Verifier returns {"verdicts": []} → every note dropped, none kept."""
    notes = _notes("claim one", "claim two", "claim three")
    with _verifier_returns([]):
        grounded, dropped = stages._verify_notes(None, _CAND, notes, "paper text")
    assert grounded == [], "no note may be kept without a grounded=true verdict"
    assert dropped == notes, "all notes must be dropped when verdicts are missing"


def test_partial_verdicts_drop_only_unmatched_notes():
    """Count mismatch → matched claims follow their verdict, unmatched are dropped."""
    notes = _notes("claim one", "claim two", "claim three")
    verdicts = [NoteVerdict(source_id="c1", claim="claim one", grounded=True),
                NoteVerdict(source_id="c1", claim="claim two", grounded=False)]
    with _verifier_returns(verdicts):
        grounded, dropped = stages._verify_notes(None, _CAND, notes, "paper text")
    assert [n.claim for n in grounded] == ["claim one"]
    assert [n.claim for n in dropped] == ["claim two", "claim three"]


def test_count_match_happy_path_unchanged():
    """One verdict per note, in order → zip path keeps/drops exactly per verdict."""
    notes = _notes("claim one", "claim two")
    verdicts = [NoteVerdict(source_id="c1", claim="claim one", grounded=True),
                NoteVerdict(source_id="c1", claim="claim two", grounded=False)]
    with _verifier_returns(verdicts):
        grounded, dropped = stages._verify_notes(None, _CAND, notes, "paper text")
    assert [n.claim for n in grounded] == ["claim one"]
    assert [n.claim for n in dropped] == ["claim two"]


# ── standalone runner (no pytest required) ───────────────────────────────────
def _main() -> int:
    tests = [
        test_empty_verdicts_drops_all_notes,
        test_partial_verdicts_drop_only_unmatched_notes,
        test_count_match_happy_path_unchanged,
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
