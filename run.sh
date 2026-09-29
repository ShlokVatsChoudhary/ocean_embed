#!/usr/bin/env bash
#
# One-command launcher for the OceanEmbed demo.
#
#   ./run.sh          start backend + frontend, open http://localhost:5173
#   ./run.sh --stop   stop anything left running from a previous start
#
# Backend:  http://localhost:8000  (API + docs at /docs)
# Frontend: http://localhost:5173  (the UI you actually look at)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173
LOG_DIR="$ROOT/.run-logs"
PID_FILE="$LOG_DIR/pids"

stop_all() {
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  # Belt and braces: catch anything started by an earlier run.
  pkill -f "uvicorn app.main:app --port $BACKEND_PORT" 2>/dev/null || true
  pkill -f "vite --port $FRONTEND_PORT" 2>/dev/null || true
  pkill -f "vite.*--port $FRONTEND_PORT" 2>/dev/null || true
}

if [[ "${1:-}" == "--stop" ]]; then
  stop_all
  echo "Stopped."
  exit 0
fi

mkdir -p "$LOG_DIR"
stop_all

# ------------------------------------------------------------------ preflight
if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 not found." >&2; exit 1
fi
if ! command -v npm >/dev/null; then
  echo "ERROR: npm not found. Install Node.js first." >&2; exit 1
fi

python3 - <<'PY' || { echo "Run:  python3 -m pip install fastapi uvicorn pydantic-settings tensorflow xarray netCDF4" >&2; exit 1; }
import importlib
for mod in ("fastapi", "uvicorn", "tensorflow", "xarray", "netCDF4", "pydantic_settings"):
    importlib.import_module(mod)
PY

if [[ ! -d "$ROOT/frontend/frontend/node_modules" ]]; then
  echo "Installing frontend dependencies (first run only)…"
  (cd "$ROOT/frontend/frontend" && npm install --silent)
fi

if [[ ! -f "$ROOT/frontend/frontend/.env" ]]; then
  echo "VITE_API_BASE=http://localhost:$BACKEND_PORT" > "$ROOT/frontend/frontend/.env"
fi

# ----------------------------------------------------------- port availability
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $port is already in use. Run ./run.sh --stop, or free the port." >&2
    exit 1
  fi
done

# ------------------------------------------------------------------- launch
: > "$PID_FILE"

echo "Starting backend on :$BACKEND_PORT …"
(cd "$ROOT/backend" && python3 -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning \
    > "$LOG_DIR/backend.log" 2>&1) &
echo $! >> "$PID_FILE"

# The model is loaded on first request, so wait for the port rather than a fixed sleep.
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
if ! curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
  echo "ERROR: backend did not become healthy. Last lines of $LOG_DIR/backend.log:" >&2
  tail -20 "$LOG_DIR/backend.log" >&2
  stop_all
  exit 1
fi
echo "  backend healthy."

echo "Starting frontend on :$FRONTEND_PORT …"
(cd "$ROOT/frontend/frontend" && npm run dev -- --port "$FRONTEND_PORT" \
    > "$LOG_DIR/frontend.log" 2>&1) &
echo $! >> "$PID_FILE"

for _ in $(seq 1 60); do
  if curl -sf "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then break; fi
  sleep 1
done

trap stop_all EXIT INT TERM

cat <<EOF

  OceanEmbed is running.

    UI    http://localhost:$FRONTEND_PORT
    API   http://127.0.0.1:$BACKEND_PORT
    Docs  http://127.0.0.1:$BACKEND_PORT/docs

  Logs    $LOG_DIR/backend.log
          $LOG_DIR/frontend.log

  Press Ctrl+C to stop, or run ./run.sh --stop in another terminal.

EOF

# Warm the model so the first click is not slow. The load takes ~20 s.
echo "Warming the model (first load ~20 s) …"
curl -sf "http://127.0.0.1:$BACKEND_PORT/api/metadata" >/dev/null 2>&1 || true
echo "  ready."

wait
