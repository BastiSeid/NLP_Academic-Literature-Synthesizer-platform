import { useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import mermaid from "mermaid";
import { RunState } from "../api";

mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "strict" });

type Tab = "review" | "rejections" | "citations" | "synthesis";

function download(name: string, content: string, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

export default function Results({ run }: { run: RunState }) {
  const [tab, setTab] = useState<Tab>("review");
  return (
    <div className="card">
      <div className="tabs">
        <button className={tab === "review" ? "active" : ""} onClick={() => setTab("review")}>📄 Literature Review</button>
        <button className={tab === "rejections" ? "active" : ""} onClick={() => setTab("rejections")}>🚫 Rejection Log ({run.rejections.length})</button>
        <button className={tab === "citations" ? "active" : ""} onClick={() => setTab("citations")}>🔖 Citations</button>
        <button className={tab === "synthesis" ? "active" : ""} onClick={() => setTab("synthesis")}>🕸 Visual Synthesis</button>
      </div>
      {tab === "review" && <Review run={run} />}
      {tab === "rejections" && <Rejections run={run} />}
      {tab === "citations" && <Citations run={run} />}
      {tab === "synthesis" && <Synthesis run={run} />}
      {run.outputs.export_paths.length > 0 && (
        <p className="muted" style={{ marginTop: 16 }}>
          💾 Exported {run.outputs.export_paths.length} files to <code>{run.outputs.export_paths[0].replace(/\/[^/]+$/, "")}</code>
        </p>
      )}
    </div>
  );
}

function Review({ run }: { run: RunState }) {
  const supportedByMarker = useMemo(() => {
    const m: Record<string, boolean> = {};
    run.verdicts.forEach((v) => { m[v.marker] = m[v.marker] || v.supported; });
    return m;
  }, [run]);

  const html = useMemo(() => {
    const raw = marked.parse(run.outputs.review_markdown || "_No review produced._", { async: false }) as string;
    let clean = DOMPurify.sanitize(raw);
    // turn [Sx] inline markers into working anchor links to the references list
    clean = clean.replace(/\[([A-Za-z0-9_]+)(\s*⚠UNVERIFIED)?\]/g,
      (_m, mk, warn) => `<a href="#cite-${mk}" class="cite">[${mk}${warn || ""}]</a>`);
    return clean;
  }, [run]);

  const refs = run.synth?.citations || [];
  const byId = Object.fromEntries(run.candidates.map((c) => [c.source_id, c]));

  return (
    <>
      <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
      <button style={{ marginTop: 12 }} onClick={() => download(`review-${run.id}.md`, run.outputs.review_markdown, "text/markdown")}>⬇ Download .md</button>
      {refs.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>References</h3>
          <ul>
            {refs.map((r, i) => {
              const c = byId[r.source_id];
              const ok = supportedByMarker[r.marker];
              return (
                <li key={i} id={`cite-${r.marker}`}>
                  <strong>[{r.marker}]</strong> {c ? c.title : r.source_id}
                  {c?.year ? ` (${c.year})` : ""} {c?.url && <a href={c.url} target="_blank" rel="noreferrer">↗</a>}
                  {" "}<span className="badge" style={{ color: ok ? "var(--green)" : "var(--red)" }}>{ok ? "verified" : "unverified"}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </>
  );
}

function Rejections({ run }: { run: RunState }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "reason_code", dir: 1 });
  const rows = [...run.rejections].sort((a: any, b: any) => {
    const x = (a[sort.key] || "").toString().toLowerCase();
    const y = (b[sort.key] || "").toString().toLowerCase();
    return x < y ? -sort.dir : x > y ? sort.dir : 0;
  });
  const h = (key: string, label: string) => (
    <th onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }))}>
      {label} {sort.key === key ? (sort.dir === 1 ? "▲" : "▼") : ""}
    </th>
  );
  if (rows.length === 0) return <p className="muted">No rejections recorded.</p>;
  return (
    <>
      <p className="muted">The moat is what's rejected — {rows.length} candidates filtered out.</p>
      <table>
        <thead><tr>{h("title", "Source")}{h("reason_code", "Reason")}{h("justification", "Justification")}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.title || r.source_id}</td>
              <td className="reason">{r.reason_code}</td>
              <td>{r.justification}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function CopyDownload({ label, content, filename, type }: { label: string; content: string; filename: string; type: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ marginBottom: 18 }}>
      <div className="row" style={{ marginBottom: 8 }}>
        <strong>{label}</strong>
        <button onClick={() => { navigator.clipboard.writeText(content); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
          {copied ? "✓ Copied" : "⧉ Copy"}
        </button>
        <button onClick={() => download(filename, content, type)}>⬇ Download</button>
      </div>
      <div className="codebox">{content || "(empty)"}</div>
    </div>
  );
}

function Citations({ run }: { run: RunState }) {
  return (
    <>
      <CopyDownload label="BibTeX" content={run.outputs.bibtex} filename={`citations-${run.id}.bib`} type="text/plain" />
      <CopyDownload label="JSON" content={run.outputs.citations_json} filename={`citations-${run.id}.json`} type="application/json" />
    </>
  );
}

function Synthesis({ run }: { run: RunState }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState("");
  const code = run.outputs.mermaid || run.synth?.mermaid || "graph TD\n  A[No diagram]";

  useEffect(() => {
    let alive = true;
    mermaid.render(`m-${run.id}`, code)
      .then(({ svg }) => { if (alive && ref.current) ref.current.innerHTML = svg; })
      .catch((e) => alive && setErr(String(e?.message || e)));
    return () => { alive = false; };
  }, [code, run.id]);

  const exportSVG = () => {
    const svg = ref.current?.querySelector("svg");
    if (svg) download(`synthesis-${run.id}.svg`, svg.outerHTML, "image/svg+xml");
  };
  const exportPNG = () => {
    const svg = ref.current?.querySelector("svg");
    if (!svg) return;
    const xml = new XMLSerializer().serializeToString(svg);
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const box = svg.getBoundingClientRect();
      canvas.width = (box.width || 800) * 2; canvas.height = (box.height || 600) * 2;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((blob) => { if (blob) { const u = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = u; a.download = `synthesis-${run.id}.png`; a.click(); URL.revokeObjectURL(u); } });
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(xml)));
  };

  return (
    <>
      {err && <div className="error">Mermaid error: {err}</div>}
      <div className="mermaid-wrap" ref={ref} />
      <div className="row" style={{ marginTop: 12 }}>
        <button onClick={exportSVG}>⬇ Export SVG</button>
        <button onClick={exportPNG}>⬇ Export PNG</button>
        <button onClick={() => download(`synthesis-${run.id}.mmd`, code, "text/plain")}>⬇ Export .mmd</button>
      </div>
    </>
  );
}
