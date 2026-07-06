from starlette.applications import Starlette
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.response import ApiResponseMiddleware


async def json_endpoint(request):
    return JSONResponse({"ok": True})


async def error_endpoint(request):
    return JSONResponse({"error": "bad"}, status_code=400)


async def stream_endpoint(request):
    async def events():
        yield "data: hello\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


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
