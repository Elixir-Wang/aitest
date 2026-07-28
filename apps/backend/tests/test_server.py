from app import server
from app import main


def test_run_configures_subsecond_graceful_shutdown(monkeypatch) -> None:
    calls = {}
    monkeypatch.delenv("APP_RELOAD", raising=False)

    def fake_run(app, **kwargs):
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(server.uvicorn, "run", fake_run)

    server.run()

    assert calls == {
        "app": "app.main:app",
        "host": "127.0.0.1",
        "port": 18000,
        "reload": False,
        "timeout_graceful_shutdown": 0.5,
    }


def test_run_allows_explicit_reload_opt_in(monkeypatch) -> None:
    calls = {}
    monkeypatch.setenv("APP_RELOAD", "1")
    monkeypatch.setattr(server.uvicorn, "run", lambda app, **kwargs: calls.update(kwargs))

    server.run()

    assert calls["reload"] is True


def test_app_shutdown_uses_non_blocking_cleanup(monkeypatch) -> None:
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
        lambda **kwargs: calls.append(("ui_automation", kwargs)),
    )
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: calls.append(("subprocess", kwargs)),
    )

    main.shutdown()

    assert calls == [
        "event_bus",
        "retention_cleanup",
        (
            "ui_automation",
            {
                "timeout": 0,
                "process_grace_seconds": 0,
                "live_view_join_timeout": 0,
            },
        ),
        ("subprocess", {"capture_output": True, "text": True, "timeout": 0.2}),
    ]


def test_ui_shutdown_forwards_zero_wait_limits(monkeypatch) -> None:
    calls = []
    service = main.ui_automation_service
    monkeypatch.setattr(
        service.live_view,
        "shutdown_all",
        lambda **kwargs: calls.append(("live_view", kwargs)),
    )
    monkeypatch.setattr(
        service.runner,
        "shutdown_all",
        lambda **kwargs: calls.append(("runner", kwargs)),
    )

    service.shutdown_background_tasks(
        timeout=0,
        process_grace_seconds=0,
        live_view_join_timeout=0,
    )

    assert calls == [
        ("live_view", {"join_timeout": 0}),
        ("runner", {"grace_seconds": 0}),
    ]
    service.prepare_background_tasks()
