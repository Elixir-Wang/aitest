from __future__ import annotations

import json
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse


async def wrap_api_response(request: Request, call_next):
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    response = await call_next(request)
    if request.method == "OPTIONS" or not request.url.path.startswith("/api/v1") or response.status_code >= 400:
        response.headers["x-trace-id"] = trace_id
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    data = json.loads(body or b"null")
    wrapped = JSONResponse(status_code=response.status_code, content={"data": data, "trace_id": trace_id})
    wrapped.headers.update(response.headers)
    if "content-length" in wrapped.headers:
        del wrapped.headers["content-length"]
    wrapped.headers["x-trace-id"] = trace_id
    return wrapped

