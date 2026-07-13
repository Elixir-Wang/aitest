# =============================================================================
# AI Testing System — All-in-One Docker Image
# Python 3.12 (FastAPI/uvicorn) + Node 22 (Next.js standalone)
# Supervisor manages both processes inside the container.
# =============================================================================

# ---------- Stage 1: build frontend ----------
FROM node:22-bookworm-slim AS frontend-builder

WORKDIR /app/frontend

RUN corepack enable

COPY apps/frontend/package.json apps/frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

COPY apps/frontend/ ./
ARG NEXT_PUBLIC_API_BASE=/api/v1
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---------- Stage 2: Python deps (uv) ----------
FROM python:3.12-slim AS python-deps

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl \
        libgl1 libglib2.0-0 libnss3 libnspr4 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libatspi2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
        libpango-1.0-0 libcairo2 libasound2 \
        fonts-noto-cjk fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY apps/backend/pyproject.toml apps/backend/uv.lock ./

RUN uv venv /app/.venv \
    && uv sync --frozen --no-dev

# ---------- Stage 3: runtime (everything in one image) ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgl1 libglib2.0-0 libnss3 libnspr4 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libatspi2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
        libpango-1.0-0 libcairo2 libasound2 \
        fonts-noto-cjk fonts-noto-color-emoji \
        nodejs npm \
        supervisor \
    && rm -rf /var/lib/apt/lists/*

# Python deps from stage 2
COPY --from=python-deps /app/.venv /app/.venv

# Backend code
COPY apps/backend/ /app/

# Frontend standalone build from stage 1
COPY --from=frontend-builder --chown=node:node /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-builder --chown=node:node /app/frontend/.next/static  /app/frontend/.next/static
COPY --from=frontend-builder --chown=node:node /app/frontend/public       /app/frontend/public

# Supervisor config + entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /app/data/projects /app/data/global-knowledge /app/data/.secrets \
             /app/logs /app/tmp /var/log/supervisor \
    && /app/.venv/bin/python -m playwright install --with-deps chromium \
    && chmod +x /entrypoint.sh

EXPOSE 3000 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -sf http://127.0.0.1:3000/ || curl -sf http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
