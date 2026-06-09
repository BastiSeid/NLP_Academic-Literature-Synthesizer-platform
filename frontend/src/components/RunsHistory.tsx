import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api";

function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return iso;
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 60) return "just now";
  const m = Math.round(s / 60); if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60); if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24); if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function RunsHistory() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.listRuns()
      .then(setRuns)
      .catch((e) => setErr(String(e?.message || e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="card">
      <h2>Runs history</h2>
      <div className="runlist" aria-busy="true">
        {[0, 1, 2].map((i) => <div key={i} className="skel" />)}
      </div>
    </div>
  );

  if (err) return <div className="card"><div className="error">Couldn't load runs: {err}</div></div>;

  if (runs.length === 0) return (
    <div className="card">
      <div className="empty">
        <div className="empty-ico">📭</div>
        <p className="muted" style={{ marginBottom: 16 }}>No runs yet.</p>
        <Link to="/"><button className="primary">＋ Start your first review</button></Link>
      </div>
    </div>
  );

  return (
    <div className="card">
      <h2>Runs history</h2>
      <ul className="runlist">
        {runs.map((r) => (
          <li key={r.id}>
            <Link className="runitem" to={`/runs/${r.id}`}
              aria-label={`${r.status.replace("_", " ")} — ${r.query}`}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <span className="q" title={r.query}>{r.query}</span>
                <span className="meta" title={new Date(r.created_at).toLocaleString()}>
                  {relTime(r.created_at)} · {r.id}
                </span>
              </div>
              <span className={"badge " + r.status}>{r.status.replace("_", " ")}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
