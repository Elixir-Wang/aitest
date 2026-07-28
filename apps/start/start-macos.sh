#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPS_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$APPS_ROOT/.." && pwd)"
BACKEND_ROOT="$APPS_ROOT/backend"
FRONTEND_ROOT="$APPS_ROOT/frontend"
LOG_ROOT="$SCRIPT_DIR/logs"

command -v uv >/dev/null 2>&1 || { echo "找不到 uv，请先安装并加入 PATH。" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "找不到 npm，请先安装并加入 PATH。" >&2; exit 1; }

mkdir -p "$LOG_ROOT"

echo "启动后端: http://127.0.0.1:18000"
(
  cd "$BACKEND_ROOT"
  exec uv run python -m app.server
) >"$LOG_ROOT/backend.log" 2>&1 &
echo $! >"$LOG_ROOT/backend.pid"

echo "启动前端: http://127.0.0.1:3000"
(
  cd "$FRONTEND_ROOT"
  exec npm run dev
) >"$LOG_ROOT/frontend.log" 2>&1 &
echo $! >"$LOG_ROOT/frontend.pid"

echo "前后端已启动。日志目录: $LOG_ROOT"
