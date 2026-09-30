#!/usr/bin/env bash
#
# One-command launcher for the OceanEmbed demo.
#
#   ./run.sh             start backend + both UIs, open the console
#   ./run.sh --console   start backend + the console UI only   (:5174)
#   ./run.sh --original  start backend + the original UI only  (:5173)
#   ./run.sh --stop      stop anything left running from a previous start
#
# Backend:  http://localhost:8000  (API + docs at /docs)
# Console:  http://localhost:5174  (the single-screen instrument UI)
# Original: http://localhost:5173  (the tabbed dashboard, kept for comparison)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT=8000
ORIGINAL_PORT=5173
CONSOLE_PORT=5174
LOG_DIR="$ROOT/.run-logs"
PID_FILE="$LOG_DIR/pids"

ORIGINAL_DIR="$ROOT/frontend/frontend"
CONSOLE_DIR="$ROOT/frontend/console"

MODE="both"
case "${1:-}" in
  --stop)     MODE="stop" ;;
  --console)  MODE="console" ;;
  --original) MODE="original" ;;
  "")         MODE="both" ;;
  *) echo "Unknown option: $1 (expected --console, --original or --stop)" >&2; exit 2 ;;
esac

stop_all() {
  if [[ -f "$PID_FILE" ]]; then
    while read -r pid; do
      [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  # Belt and braces: catch anything started by an earlier run.
  pkill -f "uvicorn app.main:app --port $BACKEND_PORT" 2>/dev/null || true
  pkill -f "vite.*--port $ORIGINAL_PORT" 2>/dev/null || true
  pkill -f "vite.*--port $CONSOLE_PORT" 2>/dev/null || true
}

if [[ "$MODE" == "stop" ]]; then
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

# Both UIs need their own dependencies and their own API base.
prepare_ui() {
  local dir="$1" port="$2" name="$3"
  if [[ ! -d "$dir/node_modules" ]]; then
    echo "Installing $name dependencies (first run only)…"
    (cd "$dir" && npm install --silent)
  fi
  if [[ ! -f "$dir/.env" ]]; then
    echo "VITE_API_BASE=http://localhost:$BACKEND_PORT" > "$dir/.env"
  fi
}

WANT_ORIGINAL=false
WANT_CONSOLE=false
case "$MODE" in
  both)     WANT_ORIGINAL=true; WANT_CONSOLE=true ;;
  original) WANT_ORIGINAL=true ;;
  console)  WANT_CONSOLE=true ;;
esac

if $WANT_ORIGINAL; then prepare_ui "$ORIGINAL_DIR" "$ORIGINAL_PORT" "original UI"; fi
if $WANT_CONSOLE;  then prepare_ui "$CONSOLE_DIR"  "$CONSOLE_PORT"  "console"; fi

# ----------------------------------------------------------- port availability
PORTS=("$BACKEND_PORT")
if $WANT_ORIGINAL; then PORTS+=("$ORIGINAL_PORT"); fi
if $WANT_CONSOLE;  then PORTS+=("$CONSOLE_PORT"); fi
for port in "${PORTS[@]}"; do
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

start_ui() {
  local dir="$1" port="$2" name="$3" log="$4"
  echo "Starting $name on :$port …"
  (cd "$dir" && npm run dev -- --port "$port" > "$LOG_DIR/$log" 2>&1) &
  echo $! >> "$PID_FILE"
  for _ in $(seq 1 60); do
    if curl -sf "http://localhost:$port/" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  if curl -sf "http://localhost:$port/" >/dev/null 2>&1; then
    echo "  $name ready."
  else
    echo "  WARNING: $name did not respond. See $LOG_DIR/$log" >&2
  fi
}

if $WANT_CONSOLE;  then start_ui "$CONSOLE_DIR"  "$CONSOLE_PORT"  "console"     console.log; fi
if $WANT_ORIGINAL; then start_ui "$ORIGINAL_DIR" "$ORIGINAL_PORT" "original UI" frontend.log; fi

trap stop_all EXIT INT TERM

{
  echo
  echo "  OceanEmbed is running."
  echo
  if $WANT_CONSOLE;  then echo "    Console   http://localhost:$CONSOLE_PORT"; fi
  if $WANT_ORIGINAL; then echo "    Original  http://localhost:$ORIGINAL_PORT"; fi
  echo "    API       http://127.0.0.1:$BACKEND_PORT"
  echo "    Docs      http://127.0.0.1:$BACKEND_PORT/docs"
  echo
  echo "  Logs    $LOG_DIR/backend.log"
  if $WANT_CONSOLE;  then echo "          $LOG_DIR/console.log"; fi
  if $WANT_ORIGINAL; then echo "          $LOG_DIR/frontend.log"; fi
  echo
  echo "  Press Ctrl+C to stop, or run ./run.sh --stop in another terminal."
  echo
}

# Warm the model so the first click is not slow. The load takes ~20 s.
echo "Warming the model (first load ~20 s) …"
curl -sf "http://127.0.0.1:$BACKEND_PORT/api/metadata" >/dev/null 2>&1 || true
echo "  ready."

wait
