# AI Testing System Backend

FastAPI + SQLite backend for first-version auth, user permission management, and model configuration.

## Run

```bash
cd apps/backend
uv sync
uv run python -m app.server
```

The server cancels active HTTP and SSE requests immediately on `Ctrl+C`.

## Test

```bash
cd apps/backend
uv run pytest
```

Seed accounts:

| Username | Password | Role |
| --- | --- | --- |
| admin | admin | 管理员 |
