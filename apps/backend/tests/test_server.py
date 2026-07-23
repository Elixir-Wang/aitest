from app import server


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
