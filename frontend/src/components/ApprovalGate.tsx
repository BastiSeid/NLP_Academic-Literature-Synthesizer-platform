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

  const editList = (list: string[], setList: (v: string[]) => void) => (
    <div className="list-edit">
      {list.map((v, i) => (
        <div className="li" key={i}>
          <input value={v} onChange={(e) => { const n = [...list]; n[i] = e.target.value; setList(n); }} />
          <button onClick={() => setList(list.filter((_, j) => j !== i))}>✕</button>
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
    <div className="card" style={{ borderColor: "var(--amber)" }}>
      <h2>⏸ Approval gate — review the plan before the expensive phases run</h2>
      <p className="muted">{plan.rationale}</p>

      {!editing ? (
        <>
          <h3>Sub-questions</h3>
          <ul>{(run.scope_plan?.sub_questions || []).map((q, i) => <li key={i}>{q}</li>)}</ul>
          <h3>Search terms</h3>
          <div className="toggle-group">{(run.scope_plan?.search_terms || []).map((t, i) => <span className="chip on" key={i}>{t}</span>)}</div>
          <h3 style={{ marginTop: 16 }}>Sources to query</h3>
          <div className="toggle-group">{(run.plan_source_set?.length ? run.plan_source_set : run.params.source_set).map((s) => <span className="chip on" key={s}>{s}</span>)}</div>

          <div className="row" style={{ marginTop: 20 }}>
            <button className="primary" onClick={approve} disabled={busy}>✓ Approve & run search</button>
            <button onClick={() => setEditing(true)} disabled={busy}>✎ Revise plan</button>
          </div>
        </>
      ) : (
        <>
          <h3>Sub-questions</h3>{editList(subs, setSubs)}
          <h3 style={{ marginTop: 16 }}>Search terms</h3>{editList(terms, setTerms)}
          <h3 style={{ marginTop: 16 }}>Sources</h3>
          <div className="toggle-group">{SOURCES.map((s) => <span key={s} className={"chip " + (sources.includes(s) ? "on" : "")} onClick={() => toggle(s)}>{s}</span>)}</div>
          <div className="row" style={{ marginTop: 20 }}>
            <button className="primary" onClick={saveRevision} disabled={busy}>Save revision</button>
            <button onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}
