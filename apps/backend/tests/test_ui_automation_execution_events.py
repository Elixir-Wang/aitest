import json
from pathlib import Path

import pytest

from app.services.ui_automation import execution_events, live_pytest_plugin


def test_event_writer_redacts_parameters_and_sequences(monkeypatch, tmp_path):
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("UI_RUN_ID", "uirun-1")
    monkeypatch.setenv("UI_RUN_EVENT_PATH", str(event_path))

    execution_events.write_event(
        "iteration_collected",
        iteration_id="iteration-0001",
        parameters={"target_model": "qwen-plus", "password": "secret-value"},
    )
    execution_events.write_event("iteration_started", iteration_id="iteration-0001")

    events, incomplete = execution_events.read_events(event_path)

    assert incomplete is False
    assert [event["sequence"] for event in events] == [1, 2]
    assert events[0]["parameters"] == {"target_model": "qwen-plus", "password": "***"}


def test_reducer_preserves_each_parameter_iteration_and_failed_step():
    events = [
        {
            "sequence": 1,
            "type": "iteration_collected",
            "iteration_id": "iteration-0001",
            "index": 0,
            "parameters": {"target_model": "qwen-plus"},
        },
        {
            "sequence": 2,
            "type": "iteration_collected",
            "iteration_id": "iteration-0002",
            "index": 1,
            "parameters": {"target_model": "gpt-5-mini"},
        },
        {"sequence": 3, "type": "iteration_started", "iteration_id": "iteration-0001"},
        {
            "sequence": 4,
            "type": "steps_defined",
            "iteration_id": "iteration-0001",
            "steps": [
                {"step_id": "step-4", "title": "选择模型", "operation_ids": ["step-3", "step-4"]},
                {"step_id": "step-5", "title": "打开历史会话", "operation_ids": ["step-5"]},
            ],
        },
        {
            "sequence": 5,
            "type": "step_started",
            "iteration_id": "iteration-0001",
            "step_id": "step-4",
            "title": "选择模型",
            "operation_ids": ["step-3", "step-4"],
        },
        {
            "sequence": 6,
            "type": "step_finished",
            "iteration_id": "iteration-0001",
            "step_id": "step-4",
            "title": "选择模型",
            "status": "failed",
            "duration_ms": 30_000,
            "error": {"type": "TimeoutError", "message": "timeout"},
            "artifacts": [{"artifact_id": "artifact-1", "relative_path": "step-artifacts/a.png"}],
        },
        {
            "sequence": 7,
            "type": "iteration_finished",
            "iteration_id": "iteration-0001",
            "status": "failed",
            "duration_ms": 30_100,
        },
    ]

    detail = execution_events.reduce_events(events, run_id="uirun-1", run_status="failed")

    assert detail["summary"]["total"] == 2
    assert detail["summary"]["failed"] == 2
    assert detail["iterations"][0]["parameters"]["target_model"] == "qwen-plus"
    assert detail["iterations"][0]["failed_step_id"] == "step-4"
    assert detail["iterations"][0]["steps"][0]["artifacts"][0]["artifact_id"] == "artifact-1"
    assert detail["iterations"][0]["steps"][1]["status"] == "skipped"


def test_reducer_preserves_error_before_first_business_step():
    events = [
        {
            "sequence": 1,
            "type": "iteration_collected",
            "iteration_id": "iteration-0001",
            "index": 0,
            "parameters": {"target_model": "qwen-plus"},
        },
        {"sequence": 2, "type": "iteration_started", "iteration_id": "iteration-0001"},
        {
            "sequence": 3,
            "type": "iteration_finished",
            "iteration_id": "iteration-0001",
            "status": "infrastructure_error",
            "duration_ms": 12,
            "error": {"type": "NameError", "message": "name 'true' is not defined"},
        },
    ]

    detail = execution_events.reduce_events(events, run_id="uirun-1", run_status="failed")

    iteration = detail["iterations"][0]
    assert iteration["status"] == "infrastructure_error"
    assert iteration["steps"] == []
    assert iteration["error"] == {"type": "NameError", "message": "name 'true' is not defined"}


def test_reader_ignores_invalid_tail_line(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps({"sequence": 1, "type": "iteration_collected", "iteration_id": "iteration-0001"})
        + "\n{invalid",
        encoding="utf-8",
    )

    events, incomplete = execution_events.read_events(path)

    assert len(events) == 1
    assert incomplete is True


def test_pytest_plugin_collects_callspec_parameters(monkeypatch, tmp_path):
    event_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("UI_RUN_ID", "uirun-collection")
    monkeypatch.setenv("UI_RUN_EVENT_PATH", str(event_path))
    monkeypatch.setenv("UI_BUSINESS_PARAMETERS", '["target_model"]')
    item = type(
        "Item",
        (),
        {
            "nodeid": "test_case.py::test_case[qwen-plus]",
            "callspec": type(
                "CallSpec",
                (),
                {"params": {"browser_name": "chromium", "target_model": "qwen-plus"}},
            )(),
        },
    )()

    live_pytest_plugin.pytest_collection_finish(type("Session", (), {"items": [item]})())

    events, _ = execution_events.read_events(event_path)
    assert item._ui_iteration_id == "iteration-0001"
    assert events[0]["parameters"] == {"target_model": "qwen-plus"}


def test_ui_case_recorder_emits_failed_step_and_screenshot(monkeypatch, tmp_path):
    event_path = tmp_path / "events.jsonl"
    artifact_root = tmp_path / "step-artifacts"
    monkeypatch.setenv("UI_RUN_ID", "uirun-step")
    monkeypatch.setenv("UI_RUN_DIR", str(tmp_path))
    monkeypatch.setenv("UI_RUN_EVENT_PATH", str(event_path))
    monkeypatch.setenv("UI_RUN_ARTIFACT_DIR", str(artifact_root))

    class Page:
        def screenshot(self, *, path, full_page):
            assert full_page is True
            target = Path(path)
            target.write_bytes(b"png")

    item = type("Item", (), {"nodeid": "test_case.py::test_case", "_ui_iteration_id": "iteration-0001"})()
    recorder = live_pytest_plugin.UiCaseRecorder(item, Page())
    recorder.define_steps([{"step_id": "step-1", "title": "打开页面", "operation_ids": ["step-1"]}])

    with pytest.raises(RuntimeError):
        with recorder.step("step-1", "打开页面", operation_ids=["step-1"]):
            raise RuntimeError("password=secret")

    events, _ = execution_events.read_events(event_path)
    finished = next(event for event in events if event["type"] == "step_finished")
    assert finished["status"] == "failed"
    assert "secret" not in finished["error"]["message"]
    assert finished["artifacts"][0]["relative_path"].startswith("step-artifacts/")


def test_failure_before_first_step_is_infrastructure_error():
    report = type("Report", (), {"failed": True, "skipped": False})()
    before_step = type("Item", (), {"_ui_step_started": False})()
    inside_step = type("Item", (), {"_ui_step_started": True})()

    assert live_pytest_plugin._iteration_status(before_step, None, report, None) == "infrastructure_error"
    assert live_pytest_plugin._iteration_status(inside_step, None, report, None) == "failed"
