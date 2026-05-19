# AI Testing System Backend

FastAPI + SQLite backend for first-version auth, user permission management, and model configuration.

## Run

```bash
cd apps/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Seed accounts:

| Username | Password | Role |
| --- | --- | --- |
| admin | admin | 管理员 |
| tester | tester123 | 测试工程师 |
| guest | guest123 | 访客 |
