#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/stop-macos.sh"
echo "重新启动服务..."
exec "$SCRIPT_DIR/start-macos.sh"
