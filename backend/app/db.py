"""SQLite persistence. A run is checkpointed as a JSON blob after every stage,
plus a few indexed columns for the history list. Survives process restart —
all writes are confined here and to the export_dir (least-privilege)."""
from __future__ import annotations

import sqlite3
from typing import Optional, List
from .config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    status      TEXT NOT NULL,
    phase       TEXT,
    cost_usd    REAL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    state_json  TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


def save_run(run_id: str, query: str, status: str, phase: str,
             cost_usd: float, created_at: str, updated_at: str,
             state_json: str) -> None:
    with _conn() as c:
        c.execute(
            """INSERT INTO runs (id, query, status, phase, cost_usd, created_at,
                                 updated_at, state_json)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status, phase=excluded.phase,
                 cost_usd=excluded.cost_usd, updated_at=excluded.updated_at,
                 state_json=excluded.state_json""",
            (run_id, query, status, phase, cost_usd, created_at, updated_at, state_json),
        )


def load_state(run_id: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute("SELECT state_json FROM runs WHERE id=?", (run_id,)).fetchone()
    return row["state_json"] if row else None


def list_runs(limit: int = 100) -> List[dict]:
    with _conn() as c:
        rows = c.execute(
            """SELECT id, query, status, phase, cost_usd, created_at, updated_at
               FROM runs ORDER BY created_at DESC LIMIT ?""", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def mark_interrupted_runs() -> None:
    """On startup, any run left mid-flight is no longer being driven."""
    active = ("scoping", "awaiting_approval", "searching", "screening",
              "extracting", "synthesizing", "verifying", "assembling")
    with _conn() as c:
        c.execute(
            f"UPDATE runs SET status='interrupted' WHERE status IN "
            f"({','.join('?' * len(active))})", active,
        )
