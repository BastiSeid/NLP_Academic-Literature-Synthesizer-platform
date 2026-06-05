import { useCallback, useEffect, useRef, useState } from "react";
import { api, RunState, ACTIVE_STATUSES } from "./api";
import NewRun from "./components/NewRun";
import Progress from "./components/Progress";
import ApprovalGate from "./components/ApprovalGate";
import Results from "./components/Results";
import RunsHistory from "./components/RunsHistory";

type View = "new" | "run" | "history";

export default function App() {
  const [view, setView] = useState<View>("new");
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [model, setModel] = useState<string>("");
  const [pollNonce, setPollNonce] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => { api.health().then((h) => setModel(h.model)).catch(() => {}); }, []);

  const refresh = useCallback(async (id: string) => {
    try {
      const r = await api.getRun(id);
      setRun(r);
      return r;
    } catch { return null; }
  }, []);

  // Poll while the run is active.
  useEffect(() => {
    if (!runId || view !== "run") return;
    let stop = false;
    const tick = async () => {
      const r = await refresh(runId);
      if (stop) return;
      if (r && ACTIVE_STATUSES.has(r.status)) {
        timer.current = window.setTimeout(tick, 1500);
      }
    };
    tick();
    return () => { stop = true; if (timer.current) window.clearTimeout(timer.current); };
  }, [runId, view, refresh, pollNonce]);

  const openRun = (id: string) => { setRunId(id); setRun(null); setView("run"); };

  return (
    <div className="app">
      <div className="topbar">
        <h1>📚 Academic Literature Synthesizer</h1>
        <span className="tag">six-stage multi-agent pipeline {model && `· ${model}`}</span>
      </div>
      <div className="nav">
        <button className={view === "new" ? "active" : ""} onClick={() => setView("new")}>＋ New Run</button>
        <button className={view === "history" ? "active" : ""} onClick={() => setView("history")}>🕘 Runs History</button>
        {runId && <button className={view === "run" ? "active" : ""} onClick={() => setView("run")}>▸ Current Run</button>}
      </div>

      {view === "new" && <NewRun onStarted={openRun} />}
      {view === "history" && <RunsHistory onOpen={openRun} />}
      {view === "run" && run && (
        <>
          <Progress run={run}
            onCancel={async () => { await api.cancel(run.id); refresh(run.id); }}
            onResume={async () => { const r = await api.resume(run.id); setRun(r); setPollNonce((n) => n + 1); }} />
          {run.status === "awaiting_approval" && (
            <ApprovalGate run={run} onChanged={() => refresh(run.id)} />
          )}
          {["done", "failed", "cancelled", "interrupted"].includes(run.status) && (
            <Results run={run} />
          )}
        </>
      )}
      {view === "run" && !run && <div className="card">Loading run…</div>}
    </div>
  );
}
