"""Headless eval runner. Drives the pipeline directly (auto-approving the gate)
and asserts the hard invariants on each case. The note-grounding gate (Stage 4)
runs inline on every case — every extracted note is checked against its own
paper's text before it can be synthesized or cited.

Usage (from backend/):
    python -m app.evals.run_evals            # run all cases
    python -m app.evals.run_evals --case overstated-abstract
    python -m app.evals.run_evals --list

NOTE: each case spends real Claude Max tokens. Start with a single case.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..schemas import RunParams
from ..pipeline.orchestrator import manager
from .. import db

CASES = json.loads((Path(__file__).parent / "cases.json").read_text())["cases"]


def _check_invariants(state) -> list[str]:
    failures = []
    kept = set(state.kept_ids)
    rejected = {r.source_id for r in state.rejections}
    # A1: no rejected source in the final citations
    if state.synth:
        for c in state.synth.citations:
            if c.source_id in rejected:
                failures.append(f"A1 violated: rejected source {c.source_id} cited")
            if c.source_id not in kept:
                failures.append(f"A1 violated: non-kept source {c.source_id} cited")
    # A4: cost cap never exceeded
    cap = state.params.cost_cap_usd or 1e9
    if state.cost_usd > cap + 1e-6 and state.status == "done":
        failures.append(f"A4 violated: cost {state.cost_usd} > cap {cap} on a completed run")
    return failures


def run_case(case: dict) -> dict:
    params = RunParams(**case.get("params", {}))
    state = manager.create_run(case["query"], params)
    ctx = manager._runs[state.id]
    manager._run_until_gate(ctx)              # scope → awaiting_approval
    if state.status == "awaiting_approval":
        state.approved = True
        manager._run_after_gate(ctx)          # heavy phases (auto-approved)

    invariant_failures = _check_invariants(state)
    return {
        "id": case["id"],
        "category": case["category"],
        "status": state.status,
        "candidates": state.counts.candidates,
        "kept": state.counts.kept,
        "rejected": state.counts.rejected,
        "notes_grounded": state.counts.notes_grounded,
        "notes_dropped": state.counts.notes_dropped,
        "cost_usd": round(state.cost_usd, 4),
        "error": state.error,
        "invariant_failures": invariant_failures,
        "ok": not invariant_failures,
    }


def main():
    db.init_db()
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for c in CASES:
            print(f"  {c['id']:24} [{c['category']}]  {c['query'][:60]}")
        return

    cases = [c for c in CASES if (not args.case or c["id"] == args.case)]
    results = []
    for c in cases:
        print(f"\n▶ {c['id']} ({c['category']})")
        t0 = time.time()
        r = run_case(c)
        r["seconds"] = round(time.time() - t0, 1)
        results.append(r)
        flag = "✅" if r["ok"] else "❌"
        print(f"  {flag} status={r['status']} kept={r['kept']} rejected={r['rejected']} "
              f"grounded={r['notes_grounded']}/{r['notes_grounded']+r['notes_dropped']} "
              f"cost=${r['cost_usd']} ({r['seconds']}s)")
        if r["invariant_failures"]:
            for f in r["invariant_failures"]:
                print(f"     ⚠ {f}")
    print("\n=== SUMMARY ===")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
