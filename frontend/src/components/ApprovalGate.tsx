import { useState } from "react";
import { api, RunState, SOURCES } from "../api";

export default function ApprovalGate({ run, onChanged }: { run: RunState; onChanged: () => void }) {
  const plan = run.scope_plan;
  const [editing, setEditing] = useState(false);
  const [subs, setSubs] = useState<string[]>(plan?.sub_questions || []);
  const [terms, setTerms] = useState<string[]>(plan?.search_terms || []);
  const [sources, setSources] = useState<string[]>(run.plan_source_set?.length ? run.plan_source_set : run.params.source_set);
  const [busy, setBusy] = useState(false);

  if (!plan) return null;

  const editList = (list: string[], setList: (v: string[]) => void, label: string) => (
    <div className="list-edit">
      {list.map((v, i) => (
        <div className="li" key={i}>
          <input value={v} aria-label={`${label} ${i + 1}`}
            onChange={(e) => { const n = [...list]; n[i] = e.target.value; setList(n); }} />
          <button className="btn-icon danger" aria-label={`Remove ${label} ${i + 1}`}
            onClick={() => setList(list.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button onClick={() => setList([...list, ""])}>＋ add</button>
    </div>
  );

  const toggle = (s: string) =>
    setSources((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const approve = async () => { setBusy(true); try { await api.approve(run.id); onChanged(); } finally { setBusy(false); } };
  const saveRevision = async () => {
    setBusy(true);
    try {
      await api.revise(run.id, { sub_questions: subs.filter(Boolean), search_terms: terms.filter(Boolean), rationale: plan.rationale }, sources);
      setEditing(false); onChanged();
    } finally { setBusy(false); }
  };

  return (
    <div className="card gate" style={{ borderLeft: "3px solid var(--warn)" }}>
      <div className="card-head">
        <h2>⏸ Approval gate</h2>
        <span className="pill warn">Action required</span>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>{plan.rationale}</p>

      {!editing ? (
        <>
          <fieldset>
            <legend>Sub-questions</legend>
            <ul style={{ margin: 0 }}>{(run.scope_plan?.sub_questions || []).map((q, i) => <li key={i}>{q}</li>)}</ul>
          </fieldset>
          <fieldset>
            <legend>Search terms</legend>
            <div className="toggle-group">{(run.scope_plan?.search_terms || []).map((t, i) => <span className="chip static on" key={i}>{t}</span>)}</div>
          </fieldset>
          <fieldset>
            <legend>Sources to query</legend>
            <div className="toggle-group">{(run.plan_source_set?.length ? run.plan_source_set : run.params.source_set).map((s) => <span className="chip static on" key={s}>{s}</span>)}</div>
          </fieldset>

          <div className="card-actions">
            <button className="primary btn-full-mobile" onClick={approve} disabled={busy}>
              {busy ? <><span className="spinner" /> Approving…</> : "✓ Approve & run search"}
            </button>
            <button onClick={() => setEditing(true)} disabled={busy}>✎ Revise plan</button>
          </div>
        </>
      ) : (
        <>
          <fieldset>
            <legend>Sub-questions</legend>
            {editList(subs, setSubs, "Sub-question")}
          </fieldset>
          <fieldset>
            <legend>Search terms</legend>
            {editList(terms, setTerms, "Search term")}
          </fieldset>
          <fieldset>
            <legend>Sources</legend>
            <div className="toggle-group" role="group" aria-label="Sources to query">
              {SOURCES.map((s) => (
                <button key={s} type="button" className={"chip " + (sources.includes(s) ? "on" : "")}
                  aria-pressed={sources.includes(s)} onClick={() => toggle(s)}>{s}</button>
              ))}
            </div>
          </fieldset>
          <div className="card-actions">
            <button className="primary btn-full-mobile" onClick={saveRevision} disabled={busy}>
              {busy ? <><span className="spinner" /> Saving…</> : "Save revision"}
            </button>
            <button onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}
