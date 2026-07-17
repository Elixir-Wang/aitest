from app.agents.page_exploration import agent as agent_module


def test_page_exploration_agent_uses_goal_prompt_and_skill(monkeypatch) -> None:
    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(agent_module, "create_deep_agent", fake_create_deep_agent)
    agent_module.page_exploration_agent(model="model", exploration_mode="goal")

    assert captured["system_prompt"] == agent_module.SYSTEM_PROMPT
    assert captured["skills"] == [
        "app/agents/page_exploration/skills/page-explorer/",
        "app/agents/page_exploration/skills/locator-best-practices/",
    ]


def test_page_exploration_agent_uses_autonomous_prompt_and_skill(monkeypatch) -> None:
    captured = {}

    def fake_create_deep_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(agent_module, "create_deep_agent", fake_create_deep_agent)
    agent_module.page_exploration_agent(model="model", exploration_mode="autonomous")

    assert captured["system_prompt"] == agent_module.AUTONOMOUS_SYSTEM_PROMPT
    assert captured["skills"] == [
        "app/agents/page_exploration/skills/autonomous-explorer/",
        "app/agents/page_exploration/skills/locator-best-practices/",
    ]
