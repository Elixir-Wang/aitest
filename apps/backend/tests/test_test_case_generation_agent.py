import pytest

from app.agents.model_selection import ModelSelection
from app.agents.test_case_generation.schemas import TestCaseGenerationInput, TestCaseGenerationResult


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


@pytest.mark.anyio
async def test_test_case_generation_disables_thinking_for_tool_strategy_models(monkeypatch) -> None:
    from app.agents.test_case_generation import service

    expected = TestCaseGenerationResult(summary="已生成测试用例。", total_count=0, modules=[])
    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {"structured_response": expected}

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-chat"),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "test_case_generation_agent", lambda model: FakeAgent())

    result = await service.generate_test_cases(
        TestCaseGenerationInput(
            requirement_name="登录需求",
            requirement_content="# 最终需求\n\n用户可以登录。",
        )
    )

    assert result is expected
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}
