from app.core import logging as app_logging


def test_setup_logging_is_idempotent(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_logging, "LOGS_DIR", tmp_path)
    app_logging.shutdown_logging()
    try:
        app_logging.setup_logging()
        first_sink_ids = app_logging._sink_ids
        app_logging.setup_logging()

        assert app_logging._sink_ids == first_sink_ids

        app_logging.shutdown_logging()
        assert app_logging._configured_level is None
        assert app_logging._sink_ids == ()
    finally:
        app_logging.shutdown_logging()
        monkeypatch.undo()
        app_logging.setup_logging()


def test_setup_logging_releases_previous_configuration(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_logging, "LOGS_DIR", tmp_path)
    app_logging.shutdown_logging()
    try:
        app_logging.setup_logging()
        first_sink_ids = app_logging._sink_ids
        app_logging.setup_logging(level="DEBUG")

        assert app_logging._configured_level == "DEBUG"
        assert app_logging._sink_ids != first_sink_ids
    finally:
        app_logging.shutdown_logging()
        monkeypatch.undo()
        app_logging.setup_logging()
