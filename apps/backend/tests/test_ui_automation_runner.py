from pathlib import Path

import pytest

from app.services.ui_automation import runner


@pytest.fixture(autouse=True)
def disable_live_view(monkeypatch):
    monkeypatch.setenv("UI_LIVE_VIEW_ENABLED", "0")


def test_run_case_executes_exact_node_and_writes_generic_result(monkeypatch, tmp_path: Path):
    captured = {}

    class Completed:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_case(
        run_id="uirun-1",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
        timeout=30,
    )

    assert captured["command"][-1] == "testcases/generated/test_login.py::test_uiauto_1"
    assert captured["kwargs"]["env"]["UI_BASE_URL"] == "https://example.test"
    assert captured["kwargs"]["env"]["UI_ARTIFACT_DIR"].endswith("run/browser")
    assert result["status"] == "passed"
    assert Path(result["result_path"]).exists()
    assert Path(result["stdout_path"]).read_text(encoding="utf-8") == "1 passed"


def test_runner_redacts_sensitive_output(monkeypatch, tmp_path: Path):
    class Completed:
        returncode = 1
        stdout = "password=secret token=abc"
        stderr = "authorization: bearer xyz"

    monkeypatch.setattr(runner.subprocess, "run", lambda *args, **kwargs: Completed())

    result = runner.run_case(
        run_id="uirun-1",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
        timeout=30,
    )

    assert "secret" not in Path(result["stdout_path"]).read_text(encoding="utf-8")
    assert "xyz" not in Path(result["stderr_path"]).read_text(encoding="utf-8")
    assert result["status"] == "failed"


def test_runner_uses_headed_browser_with_xvfb_when_enabled(monkeypatch, tmp_path: Path):
    captured = {}

    class Completed:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setenv("UI_HEADED", "1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/xvfb-run" if name == "xvfb-run" else None)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs) or Completed(),
    )

    runner.run_case(
        run_id="uirun-headed",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert captured["command"][0] == "/usr/bin/xvfb-run"
    assert "--headed" in captured["command"]
    assert "--video=on" in captured["command"]


def test_runner_collects_recorded_video(monkeypatch, tmp_path: Path):
    class Completed:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    def fake_run(command, **kwargs):
        video = tmp_path / "run" / "browser" / "case" / "video.webm"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
        return Completed()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_case(
        run_id="uirun-video",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert result["video_path"].endswith("video.webm")


def test_runner_uses_live_display_and_cleans_it_up(monkeypatch, tmp_path: Path):
    captured = {}

    class Session:
        status = "ready"
        display = ":97"

    class Completed:
        returncode = 0
        stdout = "1 passed"
        stderr = ""

    monkeypatch.setattr(runner.live_view, "start_session", lambda run_id: Session())
    monkeypatch.setattr(runner.live_view, "finish_session", lambda run_id: captured.update(finished=run_id))
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs) or Completed(),
    )

    runner.run_case(
        run_id="uirun-live",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert "--headed" in captured["command"]
    assert captured["kwargs"]["env"]["DISPLAY"] == ":97"
    assert captured["finished"] == "uirun-live"
