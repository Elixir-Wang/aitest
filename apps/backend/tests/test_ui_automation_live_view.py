import base64
import json

import pytest
import websocket

from app.services.ui_automation import live_pytest_plugin, live_view


def teardown_function():
    live_view.shutdown_all()


def _register(session: live_view.LiveViewSession) -> live_view.LiveViewSession:
    with live_view._sessions_lock:
        live_view._sessions[session.run_id] = session
    return session


def test_live_view_can_be_disabled(monkeypatch):
    monkeypatch.setenv("UI_LIVE_VIEW_ENABLED", "0")

    session = live_view.start_session("uirun-disabled")

    assert session.status == "unavailable"
    assert session.watcher is None
    assert live_view.validate_stream("uirun-disabled", "not-a-token") is None


def test_live_view_token_is_valid_while_cdp_session_is_starting_or_ready():
    session = _register(
        live_view.LiveViewSession(
            run_id="uirun-live",
            status="starting",
            message="starting",
            token="a" * 32,
            cdp_port=39521,
        )
    )

    assert live_view.validate_stream("uirun-live", "a" * 32) is session
    assert live_view.validate_stream("uirun-live", "b" * 32) is None

    session.status = "ready"
    assert live_view.validate_stream("uirun-live", "a" * 32) is session
    session.status = "ended"
    assert live_view.validate_stream("uirun-live", "a" * 32) is None


def test_mjpeg_stream_wraps_latest_cdp_frame():
    session = _register(
        live_view.LiveViewSession(
            run_id="uirun-frame",
            status="ready",
            message="ready",
            token="a" * 32,
            latest_frame=b"jpeg-data",
            frame_sequence=1,
        )
    )

    chunk = next(live_view.stream_mjpeg(session.run_id, session.token))

    assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"Content-Length: 9" in chunk
    assert chunk.endswith(b"jpeg-data\r\n")


def test_cdp_screencast_decodes_frame_and_acknowledges_it(monkeypatch):
    encoded_frame = base64.b64encode(b"jpeg-frame").decode("ascii")

    class FakeConnection:
        def __init__(self):
            self.sent = []
            self.messages = [
                json.dumps(
                    {
                        "method": "Page.screencastFrame",
                        "params": {"data": encoded_frame, "sessionId": 7},
                    }
                )
            ]

        def send(self, payload):
            self.sent.append(json.loads(payload))

        def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise websocket.WebSocketConnectionClosedException()

        def close(self):
            return None

    connection = FakeConnection()
    monkeypatch.setattr(live_view.websocket, "create_connection", lambda *args, **kwargs: connection)
    session = live_view.LiveViewSession(
        run_id="uirun-cdp",
        status="starting",
        message="starting",
        token="a" * 32,
        cdp_port=39521,
    )

    with pytest.raises(websocket.WebSocketConnectionClosedException):
        live_view._receive_frames(session, "ws://127.0.0.1/devtools/page/1")

    assert session.latest_frame == b"jpeg-frame"
    assert session.status == "ready"
    assert any(item.get("method") == "Page.screencastFrameAck" for item in connection.sent)


def test_pytest_plugin_appends_cdp_launch_arguments_after_fixture_setup(monkeypatch):
    monkeypatch.setenv("UI_LIVE_CDP_PORT", "39521")
    fixturedef = type("FixtureDef", (), {"argname": "browser_type_launch_args"})()
    launch_args = {}
    outcome = type("Outcome", (), {"get_result": lambda self: launch_args})()
    hook = live_pytest_plugin.pytest_fixture_setup(fixturedef, None)

    next(hook)
    with pytest.raises(StopIteration):
        hook.send(outcome)

    assert launch_args["args"] == [
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=39521",
        "--remote-allow-origins=*",
    ]
