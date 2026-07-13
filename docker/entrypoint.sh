#!/bin/bash
# =============================================================================
# Entrypoint: start backend + frontend under supervisor.
# =============================================================================

set -e

# Supervisor runs as root; log files written by apps need correct permissions.
# Create runtime dirs in case volume hasn't mounted yet.
mkdir -p /app/data/projects /app/data/global-knowledge /app/data/.secrets \
         /app/logs /app/tmp

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
