# Stage 1: Next.js standalone build
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /app/frontend

COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci

COPY apps/frontend/ ./
ARG NEXT_PUBLIC_API_BASE_URL=/api/v1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 2: python venv (build-essential only helps source-only wheels, not copied to runtime)
FROM python:3.12-slim AS python-deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY apps/backend/pyproject.toml apps/backend/uv.lock ./
RUN uv venv /app/.venv && uv sync --frozen --no-dev

# Stage 3: runtime
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    NEXT_TELEMETRY_DISABLED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=3000

# chromium runtime libs + CJK/emoji fonts (screenshots); curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libgl1 libglib2.0-0 libnss3 libnspr4 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libatspi2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 \
        libpango-1.0-0 libcairo2 libasound2 \
        fonts-noto-cjk fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# distro node is 18.x, too old for Next 16 — reuse the builder binary
COPY --from=frontend-builder /usr/local/bin/node /usr/local/bin/node

COPY --from=python-deps /app/.venv /app/.venv
COPY apps/backend/ /app/
COPY --from=frontend-builder /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-builder /app/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /app/frontend/public /app/frontend/public

# chromium OS deps installed above, so no --with-deps (it would re-run apt-get)
RUN /app/.venv/bin/python -m playwright install chromium

WORKDIR /app
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -sf http://127.0.0.1:3000/ || exit 1

# Backend on 127.0.0.1:18000 via the Next rewrite; node owns PID 1 for SIGTERM
CMD ["/bin/sh", "-c", "/app/.venv/bin/python -m app.server & cd /app/frontend && exec node server.js"]
