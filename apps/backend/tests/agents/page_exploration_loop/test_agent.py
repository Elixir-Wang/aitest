from app.agents.page_exploration_loop import agent as agent_module
from app.agents.page_exploration_loop.schemas import ActionDecision


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
