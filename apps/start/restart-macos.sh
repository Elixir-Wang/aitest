#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_ROOT="$APPS_ROOT/backend"
FRONTEND_ROOT="$APPS_ROOT/frontend"

stop_pid_tree() {
  local pid="$1"
  local child
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

echo "清理端口 3000 和 18000..."
stop_port 3000
stop_port 18000

while IFS= read -r pid; do
  [[ -z "$pid" ]] || stop_pid_tree "$pid"
done < <(pgrep -f "$BACKEND_ROOT.*(app\.server|uvicorn)|$FRONTEND_ROOT.*next" 2>/dev/null || true)

sleep 0.5
force_stop_port 3000
force_stop_port 18000
force_stop_matching "$BACKEND_ROOT.*(app\.server|uvicorn)|$FRONTEND_ROOT.*next"
echo "旧服务已清理，重新启动..."
exec "$SCRIPT_DIR/start-macos.sh"
