from app.services.page_exploration import runner
from app.services.page_exploration.runner import _exploration_agent_prompt


def test_autonomous_prompt_contains_compact_coverage_summary() -> None:
    prompt = _exploration_agent_prompt(
        "https://example.test/workspace",
        "autonomous",
        "工作台",
        20,
        coverage_summary={
            "completed_pages": ["page-workspace"],
            "completed_states": ["workspace.root"],
            "completed_actions": ["workspace.create_agent_trigger:click"],
            "completed_collection_groups": [
                {
                    "collection": "workspace.agent_cards",
                    "type": "自主规划Agent",
                    "status": "已发布",
                }
            ],
            "pending_collection_groups": [
                {
                    "collection": "workspace.agent_cards",
                    "type": "写作Agent",
                    "status": "草稿",
                }
            ],
        },
    )

    assert "已完成页面: page-workspace" in prompt
    assert "已完成状态: workspace.root" in prompt
    assert "已完成操作: workspace.create_agent_trigger:click" in prompt
    assert "已完成列表分组: workspace.agent_cards / 自主规划Agent / 已发布" in prompt
    assert "待探索列表分组: workspace.agent_cards / 写作Agent / 草稿" in prompt
    assert "不要重复探索以上已完成内容" in prompt
    assert "run_id" not in prompt


def test_non_autonomous_prompt_ignores_coverage_summary() -> None:
    prompt = _exploration_agent_prompt(
        "https://example.test/workspace",
        "goal",
        "工作台",
        20,
        goal="创建智能体",
        coverage_summary={"completed_pages": ["page-workspace"]},
    )

    assert "已完成页面" not in prompt


def test_autonomous_coverage_context_loads_shared_registry(monkeypatch, tmp_path) -> None:
    coverage = {"schema_version": "1.0", "pages": {"page-workspace": {"status": "complete"}}}
    expected = {"completed_pages": ["page-workspace"]}
    monkeypatch.setattr(runner, "load_coverage", lambda root, project_id: coverage)
    monkeypatch.setattr(runner, "build_autonomous_coverage_summary", lambda value: expected if value is coverage else {})

    assert runner._autonomous_coverage_context(tmp_path, "project-1", "autonomous") == expected
    assert runner._autonomous_coverage_context(tmp_path, "project-1", "goal") is None


def test_write_autonomous_coverage_uses_schema_4_artifacts(monkeypatch, tmp_path) -> None:
    updates = {"pages": [], "completed_actions": [], "collection_groups": []}
    captured = {}
    monkeypatch.setattr(
        runner,
        "coverage_updates_from_artifacts",
        lambda root, project_id: updates,
    )
    monkeypatch.setattr(
        runner,
        "update_coverage",
        lambda root, project_id, **kwargs: captured.update(
            {"root": root, "project_id": project_id, **kwargs}
        ),
    )

    runner._write_autonomous_coverage(tmp_path, "project-1", "run-1")

    assert captured == {
        "root": tmp_path,
        "project_id": "project-1",
        "run_id": "run-1",
        "mode": "autonomous",
        **updates,
    }
