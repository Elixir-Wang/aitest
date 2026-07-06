import json
import time
import uuid
from collections.abc import Callable

from loguru import logger
from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import set_trace_id

_access_logger = logger.bind(channel="access")


class ApiResponseMiddleware:
    """Wrap JSON API responses without Starlette BaseHTTPMiddleware.

    Function-style FastAPI middleware is implemented with BaseHTTPMiddleware,
    whose task-group plumbing is fragile for streaming responses and client
    disconnects on Windows. This ASGI middleware keeps stream responses on the
    direct ASGI path while preserving the existing JSON envelope contract.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        set_trace_id(trace_id)

        started_at = time.perf_counter()
        method = str(scope.get("method") or "")
        path = str(scope.get("path") or "")
        query = _query_string(scope)

        state = _ResponseState()

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.start = message
                state.status = int(message["status"])
                state.content_type = _content_type(message)
                state.passthrough = _should_passthrough(
                    method=method,
                    path=path,
                    content_type=state.content_type,
                )
                if state.passthrough:
                    _set_trace_header(message, trace_id)
                    _log_access(
                        method=method,
                        path=path,
                        query=query,
                        status=state.status,
                        elapsed_ms=_elapsed_ms(started_at),
                    )
                    await send(message)
                return

            if message["type"] != "http.response.body":
                await send(message)
                return

            if state.passthrough:
                await send(message)
                return

            state.body.extend(message.get("body", b""))
            if message.get("more_body", False):
                return

            await _send_wrapped_response(
                scope=scope,
                receive=receive,
                send=send,
                state=state,
                trace_id=trace_id,
                method=method,
                path=path,
                query=query,
                started_at=started_at,
            )

        await self.app(scope, receive, send_wrapper)


class _ResponseState:
    def __init__(self) -> None:
        self.start: Message | None = None
        self.status = 500
        self.content_type = ""
        self.passthrough = False
        self.body = bytearray()


def _should_passthrough(*, method: str, path: str, content_type: str) -> bool:
    return method == "OPTIONS" or not path.startswith("/api/v1") or "text/event-stream" in content_type


async def _send_wrapped_response(
    *,
    scope: Scope,
    receive: Receive,
    send: Send,
    state: _ResponseState,
    trace_id: str,
    method: str,
    path: str,
    query: str,
    started_at: float,
) -> None:
    if state.start is None:
        return

    _log_access(
        method=method,
        path=path,
        query=query,
        status=state.status,
        elapsed_ms=_elapsed_ms(started_at),
    )

    headers = _response_headers_without_content_length(state.start)
    body = bytes(state.body)

    if state.status >= 400 or "application/json" not in state.content_type:
        response = Response(
            content=body,
            status_code=state.status,
            headers=headers,
            media_type=None,
        )
        response.headers["x-trace-id"] = trace_id
        await response(scope, receive, send)
        return

    data = json.loads(body or b"null")
    response = JSONResponse(status_code=state.status, content={"data": data, "trace_id": trace_id})
    response.headers.update(headers)
    response.headers["x-trace-id"] = trace_id
    if "content-length" in response.headers:
        del response.headers["content-length"]
    await response(scope, receive, send)


def _response_headers_without_content_length(message: Message) -> dict[str, str]:
    headers = MutableHeaders(scope={"headers": list(message.get("headers", []))})
    if "content-length" in headers:
        del headers["content-length"]
    return dict(headers.items())


def _set_trace_header(message: Message, trace_id: str) -> None:
    headers = MutableHeaders(scope={"headers": list(message.get("headers", []))})
    headers["x-trace-id"] = trace_id
    message["headers"] = headers.raw


def _content_type(message: Message) -> str:
    headers = MutableHeaders(scope={"headers": list(message.get("headers", []))})
    return headers.get("content-type", "")


def _query_string(scope: Scope) -> str:
    raw_query = scope.get("query_string") or b""
    if not raw_query:
        return ""
    return f"?{raw_query.decode('latin-1')}"


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000


def _log_access(*, method: str, path: str, query: str, status: int, elapsed_ms: float) -> None:
    log: Callable[..., None]
    log = _access_logger.warning if status >= 400 else _access_logger.info
    log(
        "{method} {path}{query} → {status} ({elapsed:.1f}ms)",
        method=method,
        path=path,
        query=query,
        status=status,
        elapsed=elapsed_ms,
    )
