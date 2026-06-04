# Litsynth — Backlog (future features)

Deferred during the v1 bug-fix round (2026-06-04). Captured so they aren't lost.

## Self-diagnosing recovery agent
On agent timeout/failure, capture full internal logs (CLI stderr, prompts, partial
output, stage state) and add an agent that reads those logs to understand *why* it
failed and restart the stage intelligently (adjust prompt, model, or inputs).
Builds on top of the simpler "one-click resume from failed stage" shipped in v1.1.
Depends on: structured internal logging being in place first.

## Per-agent model assignment
Let each stage use a different Claude model — e.g. a cheap/fast model for screening
and search, Opus for synthesis and citation verification. The runtime already supports
a per-call `model` arg (`run_agent(..., model=...)`); this is about exposing per-stage
config in the UI/params. Can sharply cut cost and wall-clock. v1.1 ships per-*run*
model selection only.
