# Changelog

All notable changes to the **Academic Literature Synthesizer** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(`MAJOR.MINOR.PATCH`).

> **How to update this file (every session):** add new work under `## [Unreleased]`
> using the standard groups — **Added**, **Changed**, **Fixed**, **Removed**,
> **Security**. When you cut a release, rename `[Unreleased]` to the new version with a
> date (`## [0.2.0] - YYYY-MM-DD`), bump the version, and start a fresh empty
> `[Unreleased]` on top. Keep entries short, user-facing, and in past tense.

---

## [Unreleased]

### Added
- **Per-run model selector** — the New Run screen now offers a model dropdown
  (Opus 4.8 / Sonnet 4.6 / Haiku 4.5; blank = server default). Options are served by the
  backend (`LITSYNTH_AVAILABLE_MODELS`, exposed via `/health`) and the choice is threaded
  through every agent call for that run.
- **Pipeline progress bar** — the run view shows a determinate stage-progress bar with a
  percentage and current-stage caption, alongside the existing live counts.
- **One-click resume** — a failed or interrupted run can be resumed from its first not-done
  stage via `POST /api/runs/{id}/resume` and a Resume button in the run view. Completed
  stages and accumulated cost are kept (the cost cap continues); the failed stage onward
  re-runs. Interrupted runs paused at the approval gate return to the gate rather than
  auto-spending.

### Changed
- **Run view shows the full research question** instead of truncating it to 70 characters.

---

## [0.1.0] - 2026-06-04

Initial build — a runnable, end-to-end multi-agent literature-synthesis platform.
Verified with a real run: 8 candidates → 2 kept / 6 rejected, 13/13 citations verified,
all four deliverables produced and exported, zero invariant violations.

### Added
- **Six-stage multi-agent pipeline** orchestrated end-to-end: Scout (scope) → approval
  gate → Scout (retrieve) → Gatekeeper (screen/reject) → Reader (deep-read/extract) →
  Synthesizer (themes/draft) → Verifier (citation integrity) → assembly.
- **Agent runtime on the Claude Max subscription** via the headless `claude` CLI — each
  subagent is its own process with an isolated context, narrow tool scope (in-CLI tools
  disabled), and a strict Pydantic-validated JSON contract. Model configurable via
  `LITSYNTH_MODEL` (default `claude-opus-4-8`). One retry on malformed agent output.
- **Read-only data-source clients** (HTTP GET only): arXiv, Semantic Scholar, OpenAlex,
  and web (DuckDuckGo HTML) + PDF/HTML full-text fetch and cross-source dedupe.
- **UI approval gate** — pipeline pauses after scoping; user can **Approve** or **Revise**
  sub-questions, search terms, and sources before the expensive phases run.
- **Verifier loop** — unsupported claim-citation pairs route back to the Reader (bounded to
  2 rounds); remaining unsupported claims are marked `⚠UNVERIFIED`, never silently kept.
- **Four deliverables**, rendered in-UI and written to `export_dir/<run_id>/`: literature
  review (`.md`), rejection log, citations export (BibTeX + JSON), Mermaid synthesis diagram.
- **Orchestration controls / guardrails:** per-run cost cap + kill switch, wall-clock
  timeout, max-steps backstop, capped re-search/verifier rounds, live cost/token tracking.
- **Code-enforced invariants** (independent of model output): no rejected source in the
  final review; no claim attributed to an unsupporting source; no unverified claim shown as
  verified; cost cap is a hard stop; read-only on all external sources.
- **Injection guard** — all retrieved paper/web text is framed as untrusted DATA, never
  instructions.
- **Persistence** — full run state checkpointed as JSON in SQLite after every stage;
  survives process restart and page reload; reopenable from Runs History.
- **Frontend (React + TypeScript + Vite):** New Run screen with advanced params, live
  Pipeline Progress (six stages, counts, cost/tokens, Cancel), Approval Gate, Results tabs
  (sanitized markdown review with working inline citation links, sortable Rejection Log,
  BibTeX/JSON copy+download, client-side Mermaid with SVG/PNG/.mmd export), Runs History.
- **Backend (FastAPI):** run lifecycle + gate + export endpoints; CORS for local dev.
- **Eval set** — 13 saved cases (`backend/app/evals/cases.json`) incl. failure cases
  (sparse literature, overstated abstracts, ambiguous scope, tiny cost cap) + a headless
  runner that auto-approves the gate and asserts the invariants on every case.
- **Docs & ops:** README (architecture, agents, design rationale, stack, setup, eval),
  `.env.example` (no source keys required), `run.sh` one-command launcher, `.gitignore`.

### Security
- No external write access — all writes confined to the SQLite datastore and `export_dir`.
- `.env` excluded from version control; only the blank `.env.example` template is committed.

### Known limitations
- arXiv source can return HTTP 429 from shared IPs (rate limiting) and degrades gracefully
  to no results; OpenAlex, Semantic Scholar, and web keep the pipeline supplied.
- Each `claude` CLI call carries ~$0.5 / ~12s system overhead; the Reader runs per-paper
  (isolation), other stages batch to contain cost.
