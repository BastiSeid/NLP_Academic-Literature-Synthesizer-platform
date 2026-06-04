#!/usr/bin/env bash
# Launch the Academic Literature Synthesizer (backend :8000 + frontend :5173).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── backend ───────────────────────────────────────────────────────────────────
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  echo "▸ creating backend venv…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
echo "▸ starting backend on http://localhost:8000"
./.venv/bin/python -m uvicorn app.main:app --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!

# ── frontend ──────────────────────────────────────────────────────────────────
cd "$ROOT/frontend"
[ -d node_modules ] || npm install --no-audit --no-fund
echo "▸ starting frontend on http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

trap 'echo; echo "stopping…"; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true' INT TERM EXIT
echo "──────────────────────────────────────────────────"
echo "  Open  http://localhost:5173  in your browser."
echo "  Ctrl-C to stop both servers."
echo "──────────────────────────────────────────────────"
wait
