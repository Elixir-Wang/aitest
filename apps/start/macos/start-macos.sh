#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_ROOT="$(cd "$APPS_ROOT/.." && pwd)"
BACKEND_ROOT="$APPS_ROOT/backend"
FRONTEND_ROOT="$APPS_ROOT/frontend"
LOG_ROOT="$SCRIPT_DIR/logs"

command -v uv >/dev/null 2>&1 || { echo "找不到 uv，请先安装并加入 PATH。" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "找不到 npm，请先安装并加入 PATH。" >&2; exit 1; }

mkdir -p "$LOG_ROOT"

wait_for_port() {
  local name="$1"
  local port="$2"
  local pid_file="$3"
  local attempt
  for attempt in $(seq 1 60); do
    if [[ -s "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null \
      && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "$name 启动失败，日志如下：" >&2
  tail -n 40 "$LOG_ROOT/${name}.log" >&2 || true
  return 1
}

echo "启动后端: http://127.0.0.1:18000"
(
  cd "$BACKEND_ROOT"
  nohup uv run python -m app.server </dev/null >"$LOG_ROOT/backend.log" 2>&1 &
  echo $! >"$LOG_ROOT/backend.pid"
) >"$LOG_ROOT/backend.log" 2>&1 &

echo "启动前端: http://127.0.0.1:3000"
(
  cd "$FRONTEND_ROOT"
  nohup npm run dev </dev/null >"$LOG_ROOT/frontend.log" 2>&1 &
  echo $! >"$LOG_ROOT/frontend.pid"
) >"$LOG_ROOT/frontend.log" 2>&1 &

wait_for_port backend 18000 "$LOG_ROOT/backend.pid"
wait_for_port frontend 3000 "$LOG_ROOT/frontend.pid"

echo "前后端已启动。日志目录: $LOG_ROOT"
