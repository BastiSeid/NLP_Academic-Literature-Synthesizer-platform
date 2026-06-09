import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, RunParams, SOURCES } from "../api";

const MODEL_LABELS: Record<string, string> = {
  "claude-opus-4-8": "Opus 4.8 — most capable",
  "claude-sonnet-4-6": "Sonnet 4.6 — balanced, faster",
  "claude-haiku-4-5-20251001": "Haiku 4.5 — fastest, cheapest",
};

export default function NewRun() {
  const navigate = useNavigate();
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
      navigate(`/runs/${run.id}`);
    } catch (e: any) { setErr(String(e.message || e)); setBusy(false); }
  };

  return (
    <div className="card form-narrow">
      <h2>New literature review</h2>
      <div className="field">
        <label htmlFor="nr-query">Research query (broad is good — the pipeline will scope it)</label>
        <textarea id="nr-query" rows={3} value={query} onChange={(e) => setQuery(e.target.value)}
          aria-describedby="nr-query-help"
          placeholder="e.g. What are the latest advancements in multi-agent LLM systems?" />
      </div>

      <div className="field">
        <label htmlFor="nr-model">Model (blank = server default)</label>
        <select id="nr-model" value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">Server default</option>
          {models.map((m) => (
            <option key={m} value={m}>{MODEL_LABELS[m] || m}</option>
          ))}
        </select>
      </div>

      <details>
        <summary>Advanced parameters</summary>
        <div className="param-grid">
          <div className="field">
            <label htmlFor="nr-date">Date range (e.g. 2018-2026)</label>
            <input id="nr-date" value={dateRange} onChange={(e) => setDateRange(e.target.value)} placeholder="optional" />
          </div>
          <div className="field">
            <label htmlFor="nr-maxc">Max candidates</label>
            <input id="nr-maxc" type="number" inputMode="numeric" value={maxCandidates} min={5} max={200}
              onChange={(e) => setMaxCandidates(Number(e.target.value))} />
          </div>
          <div className="field">
            <label htmlFor="nr-maxk">Max kept</label>
            <input id="nr-maxk" type="number" inputMode="numeric" value={maxKept} min={1} max={60}
              onChange={(e) => setMaxKept(Number(e.target.value))} />
          </div>
          <div className="field">
            <label htmlFor="nr-cost">Cost cap (USD)</label>
            <input id="nr-cost" type="number" inputMode="decimal" value={costCap} placeholder="default"
              onChange={(e) => setCostCap(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label htmlFor="nr-export">Export directory (server-side; blank = default)</label>
          <input id="nr-export" value={exportDir} onChange={(e) => setExportDir(e.target.value)} placeholder="optional" />
        </div>
        <div className="field">
          <label>Source set</label>
          <div className="toggle-group" role="group" aria-label="Sources to query">
            {SOURCES.map((s) => (
              <button key={s} type="button" className={"chip " + (sources.includes(s) ? "on" : "")}
                aria-pressed={sources.includes(s)} onClick={() => toggle(s)}>{s}</button>
            ))}
          </div>
        </div>
      </details>

      {err && <div className="error" style={{ marginBottom: 12 }}>{err}</div>}
      <button className="primary btn-full-mobile" onClick={start} disabled={busy}>
        {busy ? <><span className="spinner" /> Starting…</> : "Start pipeline →"}
      </button>
      <p id="nr-query-help" className="callout info" style={{ marginTop: 14 }}>
        The pipeline will <strong>pause at an approval gate</strong> after scoping, before the
        expensive search / read / synthesis phases run.
      </p>
    </div>
  );
}
