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
- **Web grey-literature author & year recovery** — web/grey-literature candidates are
  no longer author-less and date-less. The web source now does a best-effort, read-only
  scrape of each result page's own bibliographic metadata (Highwire `citation_*` tags,
  JSON-LD, Dublin Core, generic `<meta name="author">`), recovering authors and the
  publication year, so these entries get real authors and a year in the APA references,
  `citations.bib`, and `citations.json` instead of falling back to title-first / `n.d.`. It is fully deterministic — no model infers names, so it adds no
  hallucination surface (the note-grounding gate is unaffected) and needs no citation
  verifier. Names in "Surname, Given" order are flipped to "Given Surname"; non-person
  strings (publishers, URLs, "Editorial Staff", etc.) are rejected, and a title-match
  guard skips pages that redirected somewhere unrelated. Pages without usable metadata
  keep `authors=[]`. Tunable via `LITSYNTH_WEB_ENRICH` (default on) and
  `LITSYNTH_WEB_ENRICH_TIMEOUT` (default 6s); fetches run in parallel and degrade
  gracefully on any failure.
- **APA 7 reference list** — the literature review now ends with an alphabetically
  sorted `## References` section rendered in APA 7th-edition style (journal-article,
  arXiv-preprint, and web variants; author initials, `& `/21+-author rules, `n.d.`
  for missing years). Each entry in `citations.json` also gains an `apa` field with
  the formatted reference string. Inline `[source_id]` markers are left intact and the
  References block is appended only at assembly, after the review is drafted, so those
  markers stay intact upstream. `citations.bib` remains valid BibTeX. Each source
  appears in the list exactly once: entries are collapsed by a union of DOI and normalized
  title, so the same paper kept under two source_ids (a DOI-bearing copy and a title-only
  copy that candidate-dedupe couldn't merge) no longer produces duplicate references.
- **Crossref source** — added `app/sources/crossref.py`, the DOI backbone (~150M
  works across every discipline) as a fifth scout source, wired into the default
  `source_set` and the search stage. JATS abstracts are stripped to plain text and
  it joins Crossref's polite pool when a contact email is configured.
- **Honest cross-source attribution** — candidates now carry `merged_from`, the list
  of *every* source that found a paper, not just the one whose copy survived dedupe.
  Previously dedupe kept the richest-abstract record (almost always OpenAlex), making
  it look as if only OpenAlex ever contributed; the other sources' hits were silently
  merged away.

- **Note-grounding gate (Stage 4)** — every Reader note is now verified against its
  own paper's full text (reused in-memory from the read — no re-fetch) and dropped if it
  is not traceable to the source, guarding against hallucinated/embellished notes before
  they can be synthesized or cited. Notes now carry a verbatim `quote`; dropped notes and
  grounded/dropped counts are persisted (`dropped_notes`, `notes_grounded`/`notes_dropped`).
  This gate is now the pipeline's sole hallucination defense — see **Removed**, where the
  Stage 6 citation Verifier was retired in favor of grounding claims at extraction.
- **Dual-screen arbiter (Stage 3)** — when the two screeners disagree on a candidate, a
  new Arbiter agent adjudicates only the disputed papers and makes the final keep/reject
  call (resolutions logged with an `ARBITER_REJECT` reason code). The fast path skips the
  arbiter entirely when the screeners agree. A new inter-screener `screen_agreement` signal
  (agree/disagree, arbiter keep/reject) is persisted for evaluation/discussion.
- **Expandable per-agent stage summaries** — each row in the pipeline view now
  expands (click to toggle, animated chevron) to reveal a human-readable summary
  of what that agent produced: the Scout's sub-questions and search terms, the
  Scout's per-source candidate breakdown, the Gatekeeper's kept/rejected counts
  and rejection-reason tally, the Reader's note counts per source, and the
  Synthesizer's themes / citation count / draft length. All derived client-side from
  existing run state — no backend changes, no added cost. Each row also labels the
  agent that ran it (Scout / Gatekeeper / Reader / Synthesizer).
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
- **HTML-first full-text reading (Reader)** — `fetch.py` now prefers an HTML version
  of each paper (including `arxiv.org/html/{id}`) and only falls back to PDF parsing
  when no HTML is available. HTML extraction is far cleaner than pypdf, which mangles
  multi-column layouts, tables, and math, so the Reader receives more faithful text.
- **Search stage shows a cumulative per-source breakdown** — the search progress detail
  now reports every source's contribution (e.g. `arxiv: 12, semantic_scholar: 18,
  openalex: 22, crossref: 15, web: 9`) instead of an overwriting line that only ever
  displayed the last source's count.
- **Screening now runs two independent screeners** with opposing dispositions — strict
  (precision-oriented, rejects when in doubt) and lenient (recall-oriented, keeps when in
  doubt) — each deciding keep/reject for *every* candidate, reconciled before the `max_kept`
  budget is applied. This replaces the single budgeted Gatekeeper and specifically targets
  the highest-impact screening error: a strong paper silently rejected.
- **More resilient source rate-limit handling** — the shared read-only HTTP helper now
  honors a server's `Retry-After` header on `429`/`503` and otherwise uses jittered
  exponential backoff, with a per-sleep cap so a hard rate-limit never stalls a request.
  Improves transient-throttle recovery across all sources (Semantic Scholar, OpenAlex,
  web). Note: arXiv's export API blocks at the IP level from some networks and sends no
  `Retry-After`, so it still degrades gracefully to no results there — those papers
  continue to arrive via Semantic Scholar and OpenAlex.
- **Run view shows the full research question** instead of truncating it to 70 characters.

### Fixed
- **No fabricated review when there are no sources** — if a run finds no candidates
  (or none survive screening, or no verifiable content can be extracted), the pipeline
  now stops before the Synthesizer and emits a short "Literature review not generated"
  message explaining no sources were found, instead of having the Synthesizer produce a
  full paper-formatted review claiming "no findings". The downstream stages are marked
  *skipped* and the run still completes cleanly. Also avoids spending agent budget on
  screening/reading/synthesis when there is nothing to analyze. A permanent, zero-cost
  regression test (`backend/tests/test_no_sources_short_circuit.py`) now guards all three
  short-circuit paths — it stubs every paid stage and asserts the Synthesizer is never
  invoked, `st.synth` stays `None`, and the review says "not generated" with no
  paper-section headers.

### Removed
- **Stage 6 citation Verifier** — the final claim-citation verification stage (and its
  bounded Verifier→Reader rework loop) has been removed. The note-grounding gate at Stage 4
  already checks every extracted note against its own paper's text *before* synthesis, so a
  claim that can't be traced to its source never reaches a citation in the first place;
  re-verifying citations afterward was redundant. The pipeline is now **five stages**.
  Dropped along with it: the `Verifier`/`stage_verify` agent and prompt, the
  `CitationVerdict`/`VerifyOutput` schemas, the `verdicts`/`verify_rounds` run-state fields,
  the `verified`/`unsupported` counts, the `LITSYNTH_MAX_VERIFY_ROUNDS` config knob, the
  `⚠UNVERIFIED` marking and the **A3** "no unverified claim shown as verified" invariant (now
  moot — there is no separate verification step to disagree with grounding). The UI's
  "citations verified" metric is replaced by a **notes-grounded** metric, and per-citation
  verified/unverified badges are removed. Code-enforced invariants A1 (no non-kept source
  cited) and A4 (cost cap is a hard stop) are unchanged.

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
