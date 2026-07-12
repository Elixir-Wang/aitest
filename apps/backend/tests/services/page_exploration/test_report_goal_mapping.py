from app.services.page_exploration.report_writer import _build_goal_action_mapping


def test_tool_event_before_plan_does_not_index_empty_step_stats():
    events = [
        {
            "type": "agent_tool_started",
            "payload": {"tool_name": "playwright_navigate_tool"},
        },
        {
            "type": "agent_plan_updated",
            "payload": {
                "plan_steps": [
                    {"description": "打开工作台", "status": "completed"},
                ]
            },
        },
    ]

    mapping = _build_goal_action_mapping(events)

    assert len(mapping) == 1
    assert mapping[0]["attempts"] >= 0
