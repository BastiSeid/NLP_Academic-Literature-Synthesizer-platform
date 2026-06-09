import { useEffect, useState } from "react";
import { Routes, Route, Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "./api";
import NewRun from "./components/NewRun";
import RunsHistory from "./components/RunsHistory";
import RunView from "./RunView";

const LAST_RUN_KEY = "litsynth:lastRun";
export const rememberRun = (id: string) => { try { localStorage.setItem(LAST_RUN_KEY, id); } catch {} };

function AppLayout() {
  const [model, setModel] = useState("");
  const [healthy, setHealthy] = useState(false);
  const [lastRun, setLastRun] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => { api.health().then((h) => { setModel(h.model); setHealthy(!!h.ok); }).catch(() => {}); }, []);

  // Re-read the last-opened run on every navigation so the "Current Run" link stays fresh.
  useEffect(() => {
    try { setLastRun(localStorage.getItem(LAST_RUN_KEY)); } catch {}
  }, [location.pathname]);

  return (
    <>
      <header className="appbar">
        <div className="appbar-inner">
          <NavLink to="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
            <span className="logo">📚</span>
            <span className="title">Literature Synthesizer</span>
          </NavLink>
          <nav className="appnav">
            <NavLink to="/" end>＋ New Run</NavLink>
            <NavLink to="/history">🕘 History</NavLink>
            {lastRun && <NavLink to={`/runs/${lastRun}`}>▸ Current Run</NavLink>}
          </nav>
          <div className="appbar-meta">
            {model && <span className="model-badge">{model}</span>}
            <span className={"health-dot" + (healthy ? " ok" : "")} title={healthy ? "API connected" : "API offline"} />
          </div>
        </div>
      </header>
      <main className="app">
        <Outlet />
      </main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<NewRun />} />
        <Route path="/history" element={<RunsHistory />} />
        <Route path="/runs/:id" element={<RunView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
