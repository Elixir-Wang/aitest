# AI Testing System Backend

FastAPI + SQLite backend for first-version auth, user permission management, and model configuration.

## Run

```bash
cd apps/backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Test

```bash
cd apps/backend
uv run pytest
```

Seed accounts:

| Username | Password | Role |
| --- | --- | --- |
| admin | admin | 管理员 |
