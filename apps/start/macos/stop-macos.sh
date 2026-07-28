#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_ROOT="$APPS_ROOT/backend"
FRONTEND_ROOT="$APPS_ROOT/frontend"
LOG_ROOT="$SCRIPT_DIR/logs"

stop_pid_tree() {
  local pid="$1"
  local child

  [[ "$pid" =~ ^[0-9]+$ ]] || return
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    stop_pid_tree "$child"
  done
  kill -TERM "$pid" 2>/dev/null || true
}

stop_port() {
  local port="$1"
  local pid

  for pid in $(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true); do
    stop_pid_tree "$pid"
  done
}

force_stop_port() {
  local port="$1"
  local pid

  for pid in $(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true); do
    kill -KILL "$pid" 2>/dev/null || true
  done
}

force_stop_matching() {
  local pattern="$1"
  local pid

  for pid in $(pgrep -f "$pattern" 2>/dev/null || true); do
    kill -KILL "$pid" 2>/dev/null || true
  done
}

echo "停止前后端服务..."
stop_port 3000
stop_port 18000

while IFS= read -r pid; do
  [[ -z "$pid" ]] || stop_pid_tree "$pid"
done < <(pgrep -f "$BACKEND_ROOT.*(app\.server|uvicorn)|$FRONTEND_ROOT.*next" 2>/dev/null || true)

sleep 0.5
force_stop_port 3000
force_stop_port 18000
force_stop_matching "$BACKEND_ROOT.*(app\.server|uvicorn)|$FRONTEND_ROOT.*next"
rm -f "$LOG_ROOT/backend.pid" "$LOG_ROOT/frontend.pid"

echo "前后端服务已停止。"
