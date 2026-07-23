import pytest


def test_manual_test_case_generation_skill_has_required_metadata() -> None:
    from pathlib import Path

    from app.agents.shared.skill_runtime import SkillDefinition

    skill_path = (
        Path(__file__).parents[1]
        / "app"
        / "agents"
        / "manual_test_case_generation"
        / "skills"
        / "manual-test-case-generation"
    )

    skill = SkillDefinition.load(skill_path)

    assert skill.name == "manual-test-case-generation"
    assert skill.description


def test_manual_test_case_prompt_contains_description_and_exploration_facts() -> None:
    from app.agents.manual_test_case_generation.schemas import (
        ExplorationContext,
        ExplorationElementContext,
        ExplorationPageContext,
        ManualTestCaseGenerationInput,
    )
    from app.agents.manual_test_case_generation.service import _build_prompt

    prompt = _build_prompt(
        ManualTestCaseGenerationInput(
            description="验证用户登录",
            exploration_context=ExplorationContext(
                pages=[
                    ExplorationPageContext(
                        page_id="page-login",
                        display_name="用户登录",
                        elements=[ExplorationElementContext(name="用户名输入框", action_type="fill")],
                    )
                ]
            ),
        )
    )

    assert "验证用户登录" in prompt
    assert "用户登录" in prompt
    assert "用户名输入框" in prompt
    assert "只返回结构化结果" in prompt


@pytest.mark.anyio
async def test_manual_test_case_generation_parses_structured_agent_result(monkeypatch) -> None:
    from app.agents.manual_test_case_generation import service
    from app.agents.manual_test_case_generation.schemas import ManualTestCaseGenerationInput

    class FakeAgent:
        async def ainvoke(self, payload):
            assert "验证用户登录" in payload["messages"][0]["content"]
            return {
                "structured_response": {
                    "title": "用户登录验证",
                    "preconditions": "用户已注册",
                    "steps": [{"action": "输入账号密码", "expected_result": "输入框展示内容"}],
                    "generation_notes": [],
                }
            }

    monkeypatch.setattr(service, "resolve_model_selection", lambda _: "selection")
    monkeypatch.setattr(service, "build_agent_model", lambda *_args, **_kwargs: "model")
    monkeypatch.setattr(service, "thinking_disabled_extra_body", lambda _: {})
    monkeypatch.setattr(service, "manual_test_case_generation_agent", lambda _: FakeAgent())

    result = await service.generate_manual_test_case(
        ManualTestCaseGenerationInput(description="验证用户登录")
    )

    assert result.title == "用户登录验证"
    assert result.steps[0].expected_result == "输入框展示内容"
