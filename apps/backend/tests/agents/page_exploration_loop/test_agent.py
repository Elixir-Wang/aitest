from app.agents.page_exploration_loop import agent as agent_module
from app.agents.page_exploration_loop.schemas import ActionDecision


def test_loop_agent_uses_independent_prompt_and_tools(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(agent_module, "get_loop_tools", lambda: ["snapshot-tool"])
    monkeypatch.setattr(agent_module, "create_deep_agent", lambda **kwargs: captured.update(kwargs) or object())

    agent_module.page_exploration_loop_agent(model="model", max_actions=55)

    assert captured["model"] == "model"
    assert captured["tools"] == ["snapshot-tool"]
    assert captured["system_prompt"] == agent_module.LOOP_SYSTEM_PROMPT
    assert "skills" not in captured


def test_loop_action_decider_uses_cross_provider_structured_output(monkeypatch) -> None:
    captured = {}
    runnable = object()

    monkeypatch.setattr(
        agent_module,
        "structured_output_runnable",
        lambda model, schema: captured.update(model=model, schema=schema) or runnable,
    )

    result = agent_module.loop_action_decider("model")

    assert result is runnable
    assert captured == {"model": "model", "schema": ActionDecision}
