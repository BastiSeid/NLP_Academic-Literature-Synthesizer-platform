import { useEffect, useState } from "react";
import { api, RunSummary } from "../api";

export default function RunsHistory({ onOpen }: { onOpen: (id: string) => void }) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.listRuns().then(setRuns).finally(() => setLoading(false)); }, []);

  if (loading) return <div className="card">Loading…</div>;
  if (runs.length === 0) return <div className="card"><p className="muted">No runs yet. Start one from “New Run”.</p></div>;

  return (
    <div className="card">
      <h2>Runs history</h2>
      <div className="runlist">
        {runs.map((r) => (
          <div key={r.id} className="runitem" onClick={() => onOpen(r.id)}>
            <div>
              <div>{r.query.slice(0, 90)}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                {new Date(r.created_at).toLocaleString()} · ${r.cost_usd.toFixed(2)} · {r.id}
              </div>
            </div>
            <span className={"badge " + r.status}>{r.status.replace("_", " ")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
