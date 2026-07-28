from app.agents.page_exploration_loop import agent as agent_module


def test_loop_agent_uses_independent_prompt_and_tools(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(agent_module, "get_loop_tools", lambda: ["snapshot-tool"])
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kwargs: captured.update(kwargs) or object())

    agent_module.page_exploration_loop_agent(model="model", max_actions=55)

    assert captured["model"] == "model"
    assert captured["tools"] == ["snapshot-tool"]
    assert captured["system_prompt"] == agent_module.LOOP_SYSTEM_PROMPT
    assert "skills" not in captured
