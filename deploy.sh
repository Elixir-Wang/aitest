#!/usr/bin/env bash
# deploy.sh —— AITest 服务器部署脚本
# 拉取最新代码并重建容器：停止旧容器 → 构建镜像 → 启动新容器。
# 数据卷始终保留，SQLite 等业务数据不会丢失。
set -Eeuo pipefail

log() { printf '==> %s\n' "$*"; }

case "${1:-}" in
  "") ;;
  --force) ;;
  -h|--help) echo '用法：bash deploy.sh [--force]'; exit 0 ;;
  *) echo "!! 未知参数：$1"; exit 1 ;;
esac

cd "$(dirname "${BASH_SOURCE[0]}")"

CMD=(docker compose -f docker-compose.yml)
if [ -f .env ]; then CMD+=(--env-file .env); fi

PORT="$(sed -n 's/^FRONTEND_PORT=//p' .env 2>/dev/null | tail -1 || true)"
PORT="${PORT:-3000}"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git fetch --prune origin "$BRANCH"

if [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ] && [ "${1:-}" != "--force" ]; then
  log "已是最新版本（$(git rev-parse --short HEAD)），未做改动"
  exit 0
fi

log "更新代码：$(git rev-parse --short HEAD) -> $(git rev-parse --short FETCH_HEAD)"
git reset --hard FETCH_HEAD
git clean -fd

log "停止旧容器"
"${CMD[@]}" down --remove-orphans

log "构建镜像"
"${CMD[@]}" build || { echo "!! 构建失败，服务已停止，请修复后重跑"; exit 1; }

log "启动容器"
"${CMD[@]}" up -d

sleep 5
"${CMD[@]}" ps
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "http://127.0.0.1:${PORT}/" || true)"
[ "$CODE" = 200 ] && log "健康检查通过：${PORT} -> 200" || log "健康检查未通过：${CODE:-无响应}"

log "部署完成：$(git rev-parse --short HEAD)"
