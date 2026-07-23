from app.services.ui_automation import live_view


def teardown_function():
    live_view.shutdown_all()


def test_live_view_reports_missing_runtime_dependencies(monkeypatch):
    monkeypatch.setattr(live_view.shutil, "which", lambda name: None)

    session = live_view.start_session("uirun-no-display")

    assert session.status == "unavailable"
    assert "Xvfb" in session.message
    assert live_view.validate_stream("uirun-no-display", "not-a-token") is None


def test_live_view_token_only_valid_for_ready_running_session():
    class RunningProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return None

    session = live_view.LiveViewSession(
        run_id="uirun-live",
        status="ready",
        message="ready",
        token="a" * 32,
        display_number=99,
        xvfb_process=RunningProcess(),
    )
    with live_view._sessions_lock:
        live_view._sessions[session.run_id] = session

    assert live_view.validate_stream("uirun-live", "a" * 32) is session
    assert live_view.validate_stream("uirun-live", "b" * 32) is None

    session.status = "ended"
    assert live_view.validate_stream("uirun-live", "a" * 32) is None
