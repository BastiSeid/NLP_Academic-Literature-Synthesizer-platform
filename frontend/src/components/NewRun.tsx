import { useEffect, useState } from "react";
import { api, RunParams, SOURCES } from "../api";

const MODEL_LABELS: Record<string, string> = {
  "claude-opus-4-8": "Opus 4.8 — most capable",
  "claude-sonnet-4-6": "Sonnet 4.6 — balanced, faster",
  "claude-haiku-4-5-20251001": "Haiku 4.5 — fastest, cheapest",
};

export default function NewRun({ onStarted }: { onStarted: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState("");
  const [maxCandidates, setMaxCandidates] = useState(80);
  const [maxKept, setMaxKept] = useState(25);
  const [costCap, setCostCap] = useState<string>("");
  const [exportDir, setExportDir] = useState("");
  const [sources, setSources] = useState<string[]>([...SOURCES]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.health().then((h) => setModels(h.models || [])).catch(() => {});
  }, []);

  const toggle = (s: string) =>
    setSources((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const start = async () => {
    setErr("");
    if (!query.trim()) { setErr("Please enter a research query."); return; }
    if (sources.length === 0) { setErr("Select at least one source."); return; }
    setBusy(true);
    const params: RunParams = {
      date_range: dateRange.trim() || null,
      max_candidates: maxCandidates,
      max_kept: maxKept,
      source_set: sources,
      export_dir: exportDir.trim() || null,
      cost_cap_usd: costCap ? Number(costCap) : null,
      model: model || null,
    };
    try {
      const run = await api.createRun(query.trim(), params);
      onStarted(run.id);
    } catch (e: any) { setErr(String(e.message || e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="card">
      <h2>New literature review</h2>
      <div className="field">
        <label>Research query (broad is good — the pipeline will scope it)</label>
        <textarea rows={3} value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What are the latest advancements in multi-agent LLM systems?" />
      </div>

      <div className="field">
        <label>Model (blank = server default)</label>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">Server default</option>
          {models.map((m) => (
            <option key={m} value={m}>{MODEL_LABELS[m] || m}</option>
          ))}
        </select>
      </div>

      <details>
        <summary>Advanced parameters</summary>
        <div className="row">
          <div className="field grow">
            <label>Date range (e.g. 2018-2026)</label>
            <input value={dateRange} onChange={(e) => setDateRange(e.target.value)} placeholder="optional" />
          </div>
          <div className="field">
            <label>Max candidates</label>
            <input type="number" value={maxCandidates} min={5} max={200}
              onChange={(e) => setMaxCandidates(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Max kept</label>
            <input type="number" value={maxKept} min={1} max={60}
              onChange={(e) => setMaxKept(Number(e.target.value))} />
          </div>
          <div className="field">
            <label>Cost cap (USD)</label>
            <input type="number" value={costCap} placeholder="default"
              onChange={(e) => setCostCap(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Export directory (server-side; blank = default)</label>
          <input value={exportDir} onChange={(e) => setExportDir(e.target.value)} placeholder="optional" />
        </div>
        <div className="field">
          <label>Source set</label>
          <div className="toggle-group">
            {SOURCES.map((s) => (
              <span key={s} className={"chip " + (sources.includes(s) ? "on" : "")}
                onClick={() => toggle(s)}>{s}</span>
            ))}
          </div>
        </div>
      </details>

      {err && <div className="error" style={{ marginBottom: 12 }}>{err}</div>}
      <button className="primary" onClick={start} disabled={busy}>
        {busy ? "Starting…" : "Start pipeline →"}
      </button>
      <p className="muted" style={{ marginTop: 10 }}>
        The pipeline will <strong>pause at an approval gate</strong> after scoping, before the
        expensive search/read/synthesis phases.
      </p>
    </div>
  );
}
