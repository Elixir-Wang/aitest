import os
from pathlib import Path

import pytest

from app.services.ui_automation import runner


@pytest.fixture(autouse=True)
def disable_live_view(monkeypatch):
    monkeypatch.setenv("UI_LIVE_VIEW_ENABLED", "0")


def _stub_process(
    monkeypatch,
    captured: dict,
    *,
    returncode: int = 0,
    stdout: str = "1 passed",
    stderr: str = "",
    on_communicate=None,
):
    class Process:
        pid = 12345

        def __init__(self, command, **kwargs):
            self.returncode = returncode
            captured["command"] = command
            captured["kwargs"] = kwargs

        def communicate(self, timeout=None):
            captured["timeout"] = timeout
            if on_communicate:
                on_communicate()
            return stdout, stderr

        def poll(self):
            return self.returncode

    monkeypatch.setattr(runner.subprocess, "Popen", Process)


def test_run_case_executes_exact_node_and_writes_generic_result(monkeypatch, tmp_path: Path):
    captured = {}

    _stub_process(monkeypatch, captured)

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
    assert Path(captured["kwargs"]["env"]["UI_ARTIFACT_DIR"]) == tmp_path / "run" / "browser"
    assert captured["kwargs"]["env"]["UI_RUN_ID"] == "uirun-1"
    assert Path(captured["kwargs"]["env"]["UI_RUN_EVENT_PATH"]) == tmp_path / "run" / "events.jsonl"
    assert Path(captured["kwargs"]["env"]["UI_RUN_ARTIFACT_DIR"]) == tmp_path / "run" / "step-artifacts"
    assert captured["kwargs"]["env"]["UI_BUSINESS_PARAMETERS"] == "[]"
    assert captured["kwargs"]["env"]["UI_RUNNER_PARENT_PID"] == str(os.getpid())
    assert captured["kwargs"]["env"]["UI_VIEWPORT_WIDTH"] == "1440"
    assert captured["kwargs"]["env"]["UI_VIEWPORT_HEIGHT"] == "900"
    assert result["status"] == "passed"
    assert result["detail_available"] is False
    assert Path(result["result_path"]).exists()
    assert Path(result["stdout_path"]).read_text(encoding="utf-8") == "1 passed"


def test_runner_redacts_sensitive_output(monkeypatch, tmp_path: Path):
    captured = {}
    _stub_process(
        monkeypatch,
        captured,
        returncode=1,
        stdout="password=secret token=abc",
        stderr="authorization: bearer xyz",
    )

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

    monkeypatch.setenv("UI_HEADED", "1")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "/usr/bin/xvfb-run" if name == "xvfb-run" else None)
    _stub_process(monkeypatch, captured)

    runner.run_case(
        run_id="uirun-headed",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert captured["timeout"] == 7200
    assert captured["command"][0] == "/usr/bin/xvfb-run"
    assert "--server-args=-screen 0 1440x900x24" in captured["command"]
    assert "--headed" in captured["command"]
    assert not any(option.startswith("--tracing=") for option in captured["command"])
    assert not any(option.startswith("--video=") for option in captured["command"])
    plugin_index = captured["command"].index("-p")
    assert captured["command"][plugin_index + 1] == "app.services.ui_automation.live_pytest_plugin"


def test_runner_does_not_collect_trace_or_video_artifacts(monkeypatch, tmp_path: Path):
    captured = {}

    def write_disabled_artifacts():
        trace = tmp_path / "run" / "browser" / "case" / "trace.zip"
        video = tmp_path / "run" / "browser" / "case" / "video.webm"
        video.parent.mkdir(parents=True, exist_ok=True)
        trace.write_bytes(b"trace")
        video.write_bytes(b"video")

    _stub_process(monkeypatch, captured, on_communicate=write_disabled_artifacts)

    result = runner.run_case(
        run_id="uirun-no-trace-video",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert "trace_path" not in result
    assert "video_path" not in result


def test_runner_passes_live_cdp_port_and_cleans_it_up(monkeypatch, tmp_path: Path):
    captured = {}

    class Session:
        status = "starting"
        cdp_port = 39521

    monkeypatch.setattr(runner.live_view, "start_session", lambda run_id: Session())
    monkeypatch.setattr(runner.live_view, "finish_session", lambda run_id: captured.update(finished=run_id))
    _stub_process(monkeypatch, captured)

    runner.run_case(
        run_id="uirun-live",
        suite_path=tmp_path / "suite",
        run_dir=tmp_path / "run",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        environment={"site_url": "https://example.test", "storage_state_path": ""},
    )

    assert "--headed" not in captured["command"]
    assert "app.services.ui_automation.live_pytest_plugin" in captured["command"]
    assert captured["kwargs"]["env"]["UI_LIVE_CDP_PORT"] == "39521"
    assert Path(captured["kwargs"]["env"]["PYTHONPATH"].split(os.pathsep)[0]) == Path(runner.__file__).parents[3]
    assert captured["finished"] == "uirun-live"


def test_request_stop_marks_run_and_terminates_active_process(monkeypatch):
    class Process:
        def poll(self):
            return None

    process = Process()
    terminated = []
    monkeypatch.setattr(runner, "_terminate_process", lambda item: terminated.append(item))
    monkeypatch.setattr(runner, "_force_kill_after_grace", lambda item: None)
    runner._PROCESSES["uirun-stop"] = process

    try:
        assert runner.request_stop("uirun-stop") is True
        assert "uirun-stop" in runner._STOP_REQUESTED
        assert terminated == [process]
    finally:
        runner._PROCESSES.pop("uirun-stop", None)
        runner.clear_stop_request("uirun-stop")


def test_shutdown_all_terminates_then_force_kills_active_processes(monkeypatch):
    class Process:
        def poll(self):
            return None

    process = Process()
    terminated = []
    monkeypatch.setattr(
        runner,
        "_terminate_process",
        lambda item, force=False: terminated.append((item, force)),
    )
    runner._PROCESSES["uirun-shutdown"] = process

    try:
        runner.shutdown_all(grace_seconds=0)

        assert "uirun-shutdown" in runner._STOP_REQUESTED
        assert terminated == [(process, False), (process, True)]
    finally:
        runner._PROCESSES.pop("uirun-shutdown", None)
        runner.clear_stop_request("uirun-shutdown")
