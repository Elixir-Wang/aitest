from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.response import ApiResponseMiddleware, ApiUnhandledExceptionMiddleware


async def json_endpoint(request):
    return JSONResponse({"ok": True})


async def error_endpoint(request):
    return JSONResponse({"error": "bad"}, status_code=400)


async def stream_endpoint(request):
    async def events():
        yield "data: hello\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


async def unhandled_error_endpoint(request):
    raise RuntimeError("database is locked")


def test_api_response_middleware_wraps_json_but_preserves_streams() -> None:
    app = Starlette(
        routes=[
            Route("/api/v1/json", json_endpoint),
            Route("/api/v1/error", error_endpoint),
            Route("/api/v1/stream", stream_endpoint),
        ]
    )
    app.add_middleware(ApiResponseMiddleware)
    client = TestClient(app)

    json_response = client.get("/api/v1/json")
    assert json_response.status_code == 200
    assert json_response.json()["data"] == {"ok": True}
    assert json_response.json()["trace_id"].startswith("trace_")
    assert json_response.headers["x-trace-id"].startswith("trace_")

    error_response = client.get("/api/v1/error")
    assert error_response.status_code == 400
    assert error_response.json() == {"error": "bad"}
    assert error_response.headers["x-trace-id"].startswith("trace_")

    stream_response = client.get("/api/v1/stream")
    assert stream_response.status_code == 200
    assert stream_response.text == "data: hello\n\n"
    assert "text/event-stream" in stream_response.headers["content-type"]
    assert stream_response.headers["x-trace-id"].startswith("trace_")


def test_unhandled_api_error_preserves_cors_and_trace_id() -> None:
    app = Starlette(routes=[Route("/api/v1/error", unhandled_error_endpoint)])
    app.add_middleware(ApiUnhandledExceptionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiResponseMiddleware)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/v1/error", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["message"] == "服务器内部错误。"
    assert response.json()["trace_id"].startswith("trace_")
    assert response.headers["x-trace-id"] == response.json()["trace_id"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
