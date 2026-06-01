import json
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.logging import set_trace_id

_access_logger = logger.bind(channel="access")


async def wrap_api_response(request: Request, call_next):
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    set_trace_id(trace_id)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    status = response.status_code
    method = request.method
    path = request.url.path
    query = f"?{request.url.query}" if request.url.query else ""

    if method == "OPTIONS" or not path.startswith("/api/v1"):
        _access_logger.info(
            "{method} {path}{query} → {status} ({elapsed:.1f}ms)",
            method=method, path=path, query=query, status=status, elapsed=elapsed_ms,
        )
        response.headers["x-trace-id"] = trace_id
        return response

    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        response.headers["x-trace-id"] = trace_id
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    if status >= 400:
        _access_logger.warning(
            "{method} {path}{query} → {status} ({elapsed:.1f}ms)",
            method=method, path=path, query=query, status=status, elapsed=elapsed_ms,
        )
        response.headers["x-trace-id"] = trace_id
        # 对于错误响应，直接返回原始 body（不包装）
        from starlette.responses import Response as StarletteResponse
        error_response = StarletteResponse(
            content=body,
            status_code=status,
            media_type=response.media_type,
        )
        error_response.headers.update(response.headers)
        if "content-length" in error_response.headers:
            del error_response.headers["content-length"]
        error_response.headers["x-trace-id"] = trace_id
        return error_response

    _access_logger.info(
        "{method} {path}{query} → {status} ({elapsed:.1f}ms)",
        method=method, path=path, query=query, status=status, elapsed=elapsed_ms,
    )

    if "application/json" not in content_type:
        from starlette.responses import Response as StarletteResponse

        raw_response = StarletteResponse(
            content=body,
            status_code=status,
            media_type=response.media_type,
        )
        raw_response.headers.update(response.headers)
        if "content-length" in raw_response.headers:
            del raw_response.headers["content-length"]
        raw_response.headers["x-trace-id"] = trace_id
        return raw_response

    data = json.loads(body or b"null")
    wrapped = JSONResponse(status_code=status, content={"data": data, "trace_id": trace_id})
    wrapped.headers.update(response.headers)
    if "content-length" in wrapped.headers:
        del wrapped.headers["content-length"]
    wrapped.headers["x-trace-id"] = trace_id
    return wrapped
