from pathlib import Path

from app.core import settings
from app.services.page_exploration.timeline_projection import (
    _coerce_tool_output_dict,
    _projection_tool_event_to_timeline_event,
)


def test_snapshot_tool_output_accepts_langchain_content_blocks():
    output = [
        {
            "type": "text",
            "text": '{"url":"https://example.test/agentStore","title":"Agent Store","elements":[]}',
        }
    ]

    parsed = _coerce_tool_output_dict(output)

    assert parsed["url"] == "https://example.test/agentStore"
    assert parsed["title"] == "Agent Store"


def test_snapshot_tool_output_accepts_json_content_block():
    output = [
        {
            "type": "json",
            "json": {
                "url": "https://example.test/workspace",
                "title": "Workspace",
                "elements": [],
            },
        }
    ]

    parsed = _coerce_tool_output_dict(output)

    assert parsed["url"].endswith("/workspace")


def test_write_todos_projection_does_not_persist_project_subgoals(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    event = _projection_tool_event_to_timeline_event(
        tool_name="write_todos",
        tool_id="todo-1",
        status="completed",
        input_data={"todos": [{"content": "打开工作台", "status": "pending"}]},
        output_data={"success": True},
        raw_event_id="event-1",
        project_id="project-1",
        run_id="run-1",
    )

    assert event is not None
    assert event["type"] == "agent_plan_updated"
    assert not (
        tmp_path / "project-1" / "page_exploration" / "subgoals.yaml"
    ).exists()
