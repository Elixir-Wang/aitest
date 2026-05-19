from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_db
from .routers import auth, dashboard, models, users

app = FastAPI(title="AI Testing System API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def wrap_api_response(request: Request, call_next):
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    response = await call_next(request)
    if request.method == "OPTIONS" or not request.url.path.startswith("/api/v1") or response.status_code >= 400:
        response.headers["x-trace-id"] = trace_id
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    import json

    data = json.loads(body or b"null")
    wrapped = JSONResponse(status_code=response.status_code, content={"data": data, "trace_id": trace_id})
    wrapped.headers.update(response.headers)
    if "content-length" in wrapped.headers:
        del wrapped.headers["content-length"]
    wrapped.headers["x-trace-id"] = trace_id
    return wrapped


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
