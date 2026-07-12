import pytest

from app.services.page_exploration.runner import (
    ExplorationStalledError,
    _ExplorationProgressGuard,
    _agent_recursion_config,
)


def test_agent_graph_budget_allows_normal_multi_step_browser_flow():
    assert _agent_recursion_config(5)["recursion_limit"] == 400
    assert _agent_recursion_config(10)["recursion_limit"] == 800


def _snapshot(url="https://example.test/page", signature="sig-1"):
    return {"data": {"output": {"url": url, "state_signature": signature}}}


def test_diagnostic_tools_do_not_reset_action_failures():
    guard = _ExplorationProgressGuard(failure_limit=3)
    guard.observe({"type": "agent_plan_updated", "payload": {"plan_steps": [{"status": "in_progress", "description": "填写 Prompt"}]}})
    guard.observe({"type": "agent_tool_completed", "payload": {"tool_name": "playwright_snap_tool"}}, _snapshot())

    failure = {"type": "agent_tool_failed", "payload": {
        "tool_name": "playwright_fill_tool",
        "element_id": "obs-1.el-1",
        "failure": {"error_type": "not_visible"},
    }}
    guard.observe(failure)
    guard.observe({"type": "agent_tool_completed", "payload": {"tool_name": "playwright_scoped_query_tool"}})
    guard.observe(failure)
    guard.observe({"type": "agent_tool_completed", "payload": {"tool_name": "playwright_observe_overlays_tool"}})
    with pytest.raises(ExplorationStalledError, match="连续失败 3 次"):
        guard.observe(failure)


def test_same_state_stops_after_total_no_progress_budget():
    guard = _ExplorationProgressGuard(failure_limit=99, no_progress_limit=3)
    guard.observe({"type": "agent_tool_completed", "payload": {"tool_name": "playwright_snap_tool"}}, _snapshot())
    diagnostic = {"type": "agent_tool_completed", "payload": {"tool_name": "playwright_scoped_query_tool"}}
    guard.observe(diagnostic)
    guard.observe(diagnostic)
    with pytest.raises(ExplorationStalledError, match="3 个动作未产生状态变化"):
        guard.observe(diagnostic)
