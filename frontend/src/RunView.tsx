import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, RunState, ACTIVE_STATUSES } from "./api";
import { rememberRun } from "./App";
import Progress from "./components/Progress";
import ApprovalGate from "./components/ApprovalGate";
import Results from "./components/Results";

export default function RunView() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunState | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [pollNonce, setPollNonce] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => { if (id) rememberRun(id); }, [id]);

  const refresh = useCallback(async (rid: string) => {
    try { const r = await api.getRun(rid); setRun(r); return r; }
    catch { setNotFound(true); return null; }
  }, []);

  // Reset when switching runs.
  useEffect(() => { setRun(null); setNotFound(false); }, [id]);

  // Poll while the run is active.
  useEffect(() => {
    if (!id) return;
    let stop = false;
    const tick = async () => {
      const r = await refresh(id);
      if (stop) return;
      if (r && ACTIVE_STATUSES.has(r.status)) {
        timer.current = window.setTimeout(tick, 1500);
      }
    };
    tick();
    return () => { stop = true; if (timer.current) window.clearTimeout(timer.current); };
  }, [id, refresh, pollNonce]);

  if (!id) return null;
  if (notFound) return <div className="card"><p className="muted">Run not found. It may have been removed.</p></div>;
  if (!run) return (
    <div className="card"><p className="muted"><span className="spinner" /> Loading run…</p></div>
  );

  return (
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
  );
}
