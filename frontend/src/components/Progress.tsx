import { useState } from "react";
import { RunState, ACTIVE_STATUSES } from "../api";

const STAGE_LABELS: Record<string, string> = {
  scope: "1 · Scope & expand",
  search: "2 · Search & retrieve",
  screen: "3 · Screen & reject",
  extract: "4 · Deep read & extract",
  synthesize: "5 · Synthesize & draft",
};

// Which agent runs each stage — shown in the expanded summary header.
const STAGE_AGENT: Record<string, string> = {
  scope: "Scout", search: "Scout", screen: "Gatekeeper",
  extract: "Reader", synthesize: "Synthesizer",
};

function tally(items: string[]): [string, number][] {
  const m: Record<string, number> = {};
  for (const k of items) m[k || "unknown"] = (m[k || "unknown"] || 0) + 1;
  return Object.entries(m).sort((a, b) => b[1] - a[1]);
}

// Human-readable summary of what a stage's agent produced, derived from RunState.
function StageSummary({ name, run }: { name: string; run: RunState }) {
  const Chips = ({ items }: { items: (string | [string, number])[] }) => (
    <div className="chips">
      {items.map((it) => {
        const [k, n] = Array.isArray(it) ? it : [it, null];
        return <span key={k} className="summchip">{k}{n !== null ? ` · ${n}` : ""}</span>;
      })}
    </div>
  );

  if (name === "scope") {
    const p = run.scope_plan;
    if (!p) return <p className="muted">Not run yet.</p>;
    return (
      <>
        {p.rationale && <p className="muted">{p.rationale}</p>}
        <div className="summlabel">Sub-questions</div>
        <ul>{p.sub_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
        <div className="summlabel">Search terms</div>
        <Chips items={p.search_terms} />
      </>
    );
  }
  if (name === "search") {
    if (run.candidates.length === 0) return <p className="muted">Not run yet.</p>;
    return (
      <>
        <p className="muted">{run.candidates.length} candidates retrieved across sources.</p>
        <Chips items={tally(run.candidates.map((c) => c.source))} />
      </>
    );
  }
  if (name === "screen") {
    if (run.kept_ids.length === 0 && run.rejections.length === 0)
      return <p className="muted">Not run yet.</p>;
    return (
      <>
        <p className="muted">{run.kept_ids.length} kept · {run.rejections.length} rejected.</p>
        {run.rejections.length > 0 && (
          <>
            <div className="summlabel">Rejection reasons</div>
            <Chips items={tally(run.rejections.map((r) => r.reason_code))} />
          </>
        )}
      </>
    );
  }
  if (name === "extract") {
    const bySource = Object.entries(run.notes || {});
    const total = bySource.reduce((n, [, v]) => n + v.length, 0);
    if (total === 0) return <p className="muted">Not run yet.</p>;
    return (
      <>
        <p className="muted">{total} reader notes across {bySource.length} sources.</p>
        <Chips items={bySource.map(([s, v]) => [s, v.length] as [string, number])} />
      </>
    );
  }
  if (name === "synthesize") {
    const s = run.synth;
    if (!s) return <p className="muted">Not run yet.</p>;
    const words = (s.review_markdown || "").trim().split(/\s+/).filter(Boolean).length;
    return (
      <>
        <p className="muted">{s.citations.length} citations · ~{words} words drafted.</p>
        {s.themes.length > 0 && (
          <>
            <div className="summlabel">Themes</div>
            <Chips items={s.themes} />
          </>
        )}
      </>
    );
  }
  return <p className="muted">No summary available.</p>;
}

// Short stepper labels (the longer "1 · Scope & expand" forms live in STAGE_LABELS).
const STEP_SHORT: Record<string, string> = {
  scope: "Scope", search: "Search", screen: "Screen", extract: "Read", synthesize: "Synthesize",
};
const STEP_ICON: Record<string, string> = { done: "✓", running: "◌", failed: "✕", skipped: "⤼" };

const PHASES = ["New", "Approval", "Running", "Results"];
function phaseIndex(status: string): number {
  if (status === "awaiting_approval") return 1;
  if (["done", "failed", "cancelled", "interrupted"].includes(status)) return 3;
  if (["created", "scoping"].includes(status)) return 0;
  return 2; // searching, screening, extracting, synthesizing, assembling
}
function bannerTone(status: string): { tone: string; text: string } {
  if (status === "awaiting_approval") return { tone: "warn", text: "Action required — review the plan below before the expensive phases run." };
  if (status === "done") return { tone: "success", text: "Pipeline complete — your literature review and deliverables are ready below." };
  if (["failed", "interrupted"].includes(status)) return { tone: "error", text: "Pipeline stopped before finishing. You can resume from where it left off." };
  if (status === "cancelled") return { tone: "error", text: "Run cancelled." };
  return { tone: "info", text: "Pipeline running — stages update live every couple of seconds." };
}

export default function Progress({ run, onCancel, onResume }: { run: RunState; onCancel: () => void; onResume: () => void }) {
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (n: string) =>
    setOpen((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x; });
  const active = ACTIVE_STATUSES.has(run.status);
  const c = run.counts;
  const total = run.stages.length || 5;
  const doneCount = run.stages.filter((s) => s.status === "done").length;
  const running = run.stages.find((s) => s.status === "running");
  const pct = run.status === "done"
    ? 100
    : Math.round(((doneCount + (running ? 0.5 : 0)) / total) * 100);
  const activeLabel = running
    ? (STAGE_LABELS[running.name] || running.name)
    : run.status.replace("_", " ");
  const phase = phaseIndex(run.status);
  const banner = bannerTone(run.status);

  return (
    <div className="card">
      <div className="card-head">
        <h2>Pipeline</h2>
        <span className={"badge " + run.status}>{run.status.replace("_", " ")}</span>
      </div>

      <div className="phasestrip" aria-label="Journey">
        {PHASES.map((p, i) => (
          <span key={p} style={{ display: "contents" }}>
            {i > 0 && <span className="sep">›</span>}
            <span className={"ph" + (i === phase ? " active" : i < phase ? " done" : "")}>{p}</span>
          </span>
        ))}
      </div>

      <div className={"status-banner " + banner.tone} role="status" aria-live="polite">{banner.text}</div>

      <p className="runquery">{run.query}</p>

      <div className="stepper" aria-hidden="true">
        {run.stages.map((s) => (
          <div key={s.name} className={"step " + s.status}>
            <div className="bar" />
            <div className="step-label">
              <span className="step-ico">{STEP_ICON[s.status] || ""}</span>
              {STEP_SHORT[s.name] || s.name}
            </div>
          </div>
        ))}
      </div>

      <div className="progressbar" role="progressbar" aria-label="pipeline progress"
        aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className={"fill" + (active ? " active" : "")} style={{ width: pct + "%" }} />
      </div>
      <div className="progresscap muted">{pct}% · {activeLabel}</div>

      <div className="metrics">
        <div className="metric"><div className="v">{c.candidates}</div><div className="l">candidates</div></div>
        <div className="metric"><div className="v" style={{ color: "var(--success)" }}>{c.kept}</div><div className="l">kept</div></div>
        <div className="metric"><div className="v" style={{ color: "var(--warn)" }}>{c.rejected}</div><div className="l">rejected</div></div>
        <div className="metric"><div className="v">{c.notes_grounded ?? 0}/{(c.notes_grounded ?? 0) + (c.notes_dropped ?? 0)}</div><div className="l">notes grounded</div></div>
      </div>

      <div className="stages">
        {run.stages.map((s) => {
          const expanded = open.has(s.name);
          const bodyId = `stage-body-${s.name}`;
          return (
            <div key={s.name} className={"stage " + s.status}>
              <button className="stage-head" aria-expanded={expanded} aria-controls={bodyId}
                onClick={() => toggle(s.name)}>
                <span className="dot" />
                <span className="name">{STAGE_LABELS[s.name] || s.name}</span>
                <span className="detail">{s.detail || s.status}</span>
                <span className="agent">{STAGE_AGENT[s.name]}</span>
                <span className={"chevron" + (expanded ? " open" : "")}>▸</span>
              </button>
              {expanded && (
                <div className="stage-body" id={bodyId}>
                  <StageSummary name={s.name} run={run} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {run.error && <div className="error" style={{ marginTop: 12 }}>⚠ {run.error}</div>}

      {(active || run.status === "failed" || run.status === "interrupted") && (
        <div className="card-actions">
          {active && (
            <button className="danger" onClick={onCancel}>■ Cancel run (kill switch)</button>
          )}
          {(run.status === "failed" || run.status === "interrupted") && (
            <>
              <button className="primary" onClick={onResume}>↻ Resume from where it stopped</button>
              <span className="muted">re-runs the failed stage onward; completed stages are kept</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
