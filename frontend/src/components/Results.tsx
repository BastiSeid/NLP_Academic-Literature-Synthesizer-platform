import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { marked } from "marked";
import DOMPurify from "dompurify";
import mermaid from "mermaid";
import { RunState } from "../api";

mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "strict" });

type Tab = "review" | "rejections" | "citations" | "synthesis";
const TAB_ORDER: Tab[] = ["review", "rejections", "citations", "synthesis"];

function download(name: string, content: string, type = "text/plain") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  URL.revokeObjectURL(url);
}

const TAB_LABELS: Record<Tab, string> = {
  review: "📄 Literature Review",
  rejections: "🚫 Rejection Log",
  citations: "🔖 Citations",
  synthesis: "🕸 Visual Synthesis",
};

export default function Results({ run }: { run: RunState }) {
  const [sp, setSp] = useSearchParams();
  const raw = sp.get("tab") as Tab | null;
  const tab: Tab = raw && TAB_ORDER.includes(raw) ? raw : "review";
  const select = (t: Tab) => setSp((prev) => { prev.set("tab", t); return prev; }, { replace: true });

  const onKey = (e: React.KeyboardEvent) => {
    const i = TAB_ORDER.indexOf(tab);
    if (e.key === "ArrowRight") { e.preventDefault(); select(TAB_ORDER[(i + 1) % TAB_ORDER.length]); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); select(TAB_ORDER[(i - 1 + TAB_ORDER.length) % TAB_ORDER.length]); }
  };

  return (
    <div className="card">
      <div className="tabs" role="tablist" aria-label="Results" onKeyDown={onKey}>
        {TAB_ORDER.map((t) => (
          <button key={t} role="tab" id={`tab-${t}`} aria-controls={`panel-${t}`}
            aria-selected={tab === t} tabIndex={tab === t ? 0 : -1} onClick={() => select(t)}>
            {TAB_LABELS[t]}{t === "rejections" ? ` (${run.rejections.length})` : ""}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {tab === "review" && <Review run={run} />}
        {tab === "rejections" && <Rejections run={run} />}
        {tab === "citations" && <Citations run={run} />}
        {tab === "synthesis" && <Synthesis run={run} />}
      </div>
      {run.outputs.export_paths.length > 0 && (
        <p className="callout info" style={{ marginTop: 16 }}>
          💾 Exported {run.outputs.export_paths.length} files to <code>{run.outputs.export_paths[0].replace(/\/[^/]+$/, "")}</code>
        </p>
      )}
    </div>
  );
}

function Review({ run }: { run: RunState }) {
  const html = useMemo(() => {
    const raw = marked.parse(run.outputs.review_markdown || "_No review produced._", { async: false }) as string;
    let clean = DOMPurify.sanitize(raw);
    // turn [Sx] inline markers into working anchor links to the references list
    clean = clean.replace(/\[([A-Za-z0-9_]+)\]/g,
      (_m, mk) => `<a href="#cite-${mk}" class="cite">[${mk}]</a>`);
    return clean;
  }, [run]);

  const refs = run.synth?.citations || [];
  const byId = Object.fromEntries(run.candidates.map((c) => [c.source_id, c]));

  return (
    <div className="measure">
      <button style={{ marginBottom: 16 }} onClick={() => download(`review-${run.id}.md`, run.outputs.review_markdown, "text/markdown")}>⬇ Download .md</button>
      <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />
      {refs.length > 0 && (
        <>
          <h3 style={{ marginTop: 24 }}>References</h3>
          <ul>
            {refs.map((r, i) => {
              const c = byId[r.source_id];
              return (
                <li key={i} id={`cite-${r.marker}`}>
                  <strong>[{r.marker}]</strong> {c ? c.title : r.source_id}
                  {c?.year ? ` (${c.year})` : ""} {c?.url && <a href={c.url} target="_blank" rel="noreferrer">↗</a>}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

function Rejections({ run }: { run: RunState }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "reason_code", dir: 1 });
  const rows = [...run.rejections].sort((a: any, b: any) => {
    const x = (a[sort.key] || "").toString().toLowerCase();
    const y = (b[sort.key] || "").toString().toLowerCase();
    return x < y ? -sort.dir : x > y ? sort.dir : 0;
  });
  const h = (key: string, label: string) => {
    const ariaSort = sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none";
    return (
      <th aria-sort={ariaSort as any}>
        <button onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : 1 }))}>
          {label} {sort.key === key ? (sort.dir === 1 ? "▲" : "▼") : ""}
        </button>
      </th>
    );
  };
  if (rows.length === 0) return <p className="muted">No rejections recorded.</p>;
  return (
    <>
      <p className="muted">The moat is what's rejected — {rows.length} candidates filtered out.</p>
      <div className="table-scroll">
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
      </div>
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
  const viewportRef = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState("");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [fs, setFs] = useState(false);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const code = run.outputs.mermaid || run.synth?.mermaid || "graph TD\n  A[No diagram]";

  useEffect(() => {
    let alive = true;
    mermaid.render(`m-${run.id}`, code)
      .then(({ svg }) => { if (alive && ref.current) ref.current.innerHTML = svg; })
      .catch((e) => alive && setErr(String(e?.message || e)));
    return () => { alive = false; };
  }, [code, run.id]);

  // Wheel zoom via a non-passive listener so the page doesn't scroll.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setZoom((z) => Math.min(5, Math.max(0.2, z * (e.deltaY < 0 ? 1.1 : 0.9))));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // Escape exits fullscreen.
  useEffect(() => {
    if (!fs) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFs(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fs]);

  const onDown = (e: { clientX: number; clientY: number }) => {
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };
  const onMove = (e: { clientX: number; clientY: number }) => {
    if (drag.current) setPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y });
  };
  const onUp = () => { drag.current = null; };
  const reset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

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
      <div className={"mermaid-viewport" + (fs ? " fs" : "")} ref={viewportRef}
        onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
        <div className="mermaid-stage" ref={ref}
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }} />
        <div className="mermaid-controls" onMouseDown={(e) => e.stopPropagation()}>
          <button onClick={() => setZoom((z) => Math.min(5, z * 1.2))} title="Zoom in" aria-label="Zoom in">＋</button>
          <button onClick={() => setZoom((z) => Math.max(0.2, z / 1.2))} title="Zoom out" aria-label="Zoom out">－</button>
          <span className="mermaid-zoomlabel">{Math.round(zoom * 100)}%</span>
          <button onClick={reset} title="Reset view" aria-label="Reset view">⟳</button>
          <button onClick={() => setFs((v) => !v)} title={fs ? "Exit fullscreen (Esc)" : "Fullscreen"} aria-label={fs ? "Exit fullscreen" : "Fullscreen"}>{fs ? "✕" : "⛶"}</button>
        </div>
      </div>
      <div className="row" style={{ marginTop: 12 }}>
        <button onClick={exportSVG}>⬇ Export SVG</button>
        <button onClick={exportPNG}>⬇ Export PNG</button>
        <button onClick={() => download(`synthesis-${run.id}.mmd`, code, "text/plain")}>⬇ Export .mmd</button>
      </div>
    </>
  );
}
