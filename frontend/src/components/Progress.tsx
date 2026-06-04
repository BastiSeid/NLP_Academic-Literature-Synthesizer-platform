import { RunState, ACTIVE_STATUSES } from "../api";

const STAGE_LABELS: Record<string, string> = {
  scope: "1 · Scope & expand",
  search: "2 · Search & retrieve",
  screen: "3 · Screen & reject",
  extract: "4 · Deep read & extract",
  synthesize: "5 · Synthesize & draft",
  verify: "6 · Verify citations",
};

export default function Progress({ run, onCancel }: { run: RunState; onCancel: () => void }) {
  const active = ACTIVE_STATUSES.has(run.status);
  const c = run.counts;
  const total = run.stages.length || 6;
  const doneCount = run.stages.filter((s) => s.status === "done").length;
  const running = run.stages.find((s) => s.status === "running");
  const pct = run.status === "done"
    ? 100
    : Math.round(((doneCount + (running ? 0.5 : 0)) / total) * 100);
  const activeLabel = running
    ? (STAGE_LABELS[running.name] || running.name)
    : run.status.replace("_", " ");
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Pipeline</h2>
        <span className={"badge " + run.status}>{run.status.replace("_", " ")}</span>
      </div>
      <p className="runquery">{run.query}</p>

      <div className="progressbar" role="progressbar"
        aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className={"fill" + (active ? " active" : "")} style={{ width: pct + "%" }} />
      </div>
      <div className="progresscap muted">{pct}% · {activeLabel}</div>

      <div className="metrics">
        <div className="metric"><div className="v">{c.candidates}</div><div className="l">candidates</div></div>
        <div className="metric"><div className="v" style={{ color: "var(--green)" }}>{c.kept}</div><div className="l">kept</div></div>
        <div className="metric"><div className="v" style={{ color: "var(--amber)" }}>{c.rejected}</div><div className="l">rejected</div></div>
        <div className="metric"><div className="v">{c.verified}/{c.verified + c.unsupported}</div><div className="l">citations verified</div></div>
        <div className="metric"><div className="v">${run.cost_usd.toFixed(2)}</div><div className="l">cost</div></div>
        <div className="metric"><div className="v">{((run.tokens_in + run.tokens_out) / 1000).toFixed(0)}k</div><div className="l">tokens</div></div>
      </div>

      <div className="stages">
        {run.stages.map((s) => (
          <div key={s.name} className={"stage " + s.status}>
            <span className="dot" />
            <span className="name">{STAGE_LABELS[s.name] || s.name}</span>
            <span className="detail">{s.detail || s.status}</span>
          </div>
        ))}
      </div>

      {run.verify_rounds > 0 && (
        <p className="muted" style={{ marginTop: 10 }}>
          ↩ Verifier sent unsupported claims back to the Reader · round {run.verify_rounds}
        </p>
      )}
      {run.error && <div className="error" style={{ marginTop: 12 }}>⚠ {run.error}</div>}

      {active && (
        <div style={{ marginTop: 14 }}>
          <button className="danger" onClick={onCancel}>■ Cancel run (kill switch)</button>
        </div>
      )}
    </div>
  );
}
