from pathlib import Path

import yaml

from app.services.page_exploration.coverage_evaluator import evaluate_autonomous_coverage


def test_autonomous_coverage_requires_all_discovered_elements_to_be_executed(tmp_path: Path) -> None:
    page_dir = tmp_path / "project-1" / "page_exploration" / "pages"
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-1"
    page_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (page_dir / "page-workspace.yaml").write_text(
        yaml.safe_dump({"elements": [{"key": "button:create"}, {"key": "button:delete"}]}),
        encoding="utf-8",
    )
    (run_dir / "timeline_events.jsonl").write_text(
        '{"type":"agent_tool_completed","payload":{"tool_name":"playwright_click_tool","element_key":"button:create"}}\n',
        encoding="utf-8",
    )

    result = evaluate_autonomous_coverage(tmp_path, "project-1", "run-1")

    assert result["discovered"] == 2
    assert result["executed"] == 1
    assert result["pending"] == 1
    assert result["complete"] is False


def test_autonomous_coverage_requires_cleanup_after_creation(tmp_path: Path) -> None:
    page_dir = tmp_path / "project-1" / "page_exploration" / "pages"
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-1"
    page_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (page_dir / "page-workspace.yaml").write_text(
        yaml.safe_dump({"elements": [{"key": "button:create"}, {"key": "button:delete"}]}),
        encoding="utf-8",
    )
    (run_dir / "timeline_events.jsonl").write_text(
        "\n".join([
            '{"type":"agent_tool_completed","payload":{"tool_name":"playwright_click_tool","element_key":"button:create"}}',
            '{"type":"agent_tool_completed","payload":{"tool_name":"playwright_click_tool","element_key":"button:delete"}}',
        ]) + "\n",
        encoding="utf-8",
    )

    result = evaluate_autonomous_coverage(tmp_path, "project-1", "run-1")

    assert result["created_actions"] == 1
    assert result["cleanup_actions"] == 1
    assert result["cleanup_pending"] == 0
