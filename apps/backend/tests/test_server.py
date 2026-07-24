from app import server
from app import main


def test_run_configures_immediate_graceful_shutdown(monkeypatch) -> None:
    calls = {}

    def fake_run(app, **kwargs):
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(server.uvicorn, "run", fake_run)

    server.run()

    assert calls == {
        "app": "app.main:app",
        "host": "127.0.0.1",
        "port": 8000,
        "reload": True,
        "timeout_graceful_shutdown": 0,
    }


def test_app_shutdown_stops_ui_automation_tasks(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(main.event_bus, "close_all", lambda: calls.append("event_bus"))
    monkeypatch.setattr(
        main.retention_cleanup_service,
        "shutdown_cleanup",
        lambda: calls.append("retention_cleanup"),
    )
    monkeypatch.setattr(
        main.ui_automation_service,
        "shutdown_background_tasks",
        lambda: calls.append("ui_automation"),
    )
    monkeypatch.setattr(main, "shutdown_logging", lambda: calls.append("logging"))
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: None)

    main.shutdown()

    assert calls == ["event_bus", "retention_cleanup", "ui_automation", "logging"]
