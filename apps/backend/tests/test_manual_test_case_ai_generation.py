import pytest
from pydantic import ValidationError


def test_manual_test_case_ai_step_requires_action_and_expected_result() -> None:
    from app.agents.manual_test_case_generation.schemas import ManualTestCaseGenerationStep

    step = ManualTestCaseGenerationStep(action="  点击登录  ", expected_result="  登录成功  ")

    assert step.action == "点击登录"
    assert step.expected_result == "登录成功"

    with pytest.raises(ValidationError):
        ManualTestCaseGenerationStep(action="点击登录", expected_result="")


def test_manual_test_case_ai_input_requires_description() -> None:
    from app.agents.manual_test_case_generation.schemas import ManualTestCaseAiGenerateIn

    with pytest.raises(ValidationError):
        ManualTestCaseAiGenerateIn(description=" ")


@pytest.mark.anyio
async def test_preview_generation_returns_structured_result_without_persisting(monkeypatch) -> None:
    from app.agents.manual_test_case_generation.schemas import (
        ManualTestCaseGenerationResult,
        ManualTestCaseGenerationStep,
    )
    from app.services.manual_test_case_generation import service

    expected = ManualTestCaseGenerationResult(
        title="登录成功验证",
        preconditions="用户已注册",
        steps=[ManualTestCaseGenerationStep(action="输入有效账号密码并登录", expected_result="进入首页")],
        generation_notes=[],
    )

    async def fake_generate(input_data):
        assert input_data.description == "验证用户可以正常登录"
        assert input_data.exploration_context is None
        return expected

    monkeypatch.setattr(service, "generate_manual_test_case", fake_generate)

    result = await service.generate_manual_test_case_preview(
        actor={"id": "u-admin", "role": "admin"},
        project_id="project-1",
        payload=service.ManualTestCaseAiGenerateIn(
            description="验证用户可以正常登录",
            include_exploration_artifacts=False,
        ),
    )

    assert result.title == expected.title
    assert result.steps[0].expected_result == "进入首页"
    assert result.source_summary.exploration_artifacts_used is False


@pytest.mark.anyio
async def test_preview_generation_degrades_when_project_has_no_exploration_artifacts(monkeypatch) -> None:
    from app.agents.manual_test_case_generation.schemas import ManualTestCaseGenerationResult
    from app.services.manual_test_case_generation import service

    monkeypatch.setattr(service, "build_exploration_context", lambda **_: None)

    async def fake_generate(input_data):
        assert input_data.exploration_context is None
        return ManualTestCaseGenerationResult(
            title="无产物场景",
            preconditions="",
            steps=[{"action": "执行操作", "expected_result": "看到结果"}],
            generation_notes=[],
        )

    monkeypatch.setattr(service, "generate_manual_test_case", fake_generate)

    result = await service.generate_manual_test_case_preview(
        actor={"id": "u-admin", "role": "admin"},
        project_id="project-1",
        payload=service.ManualTestCaseAiGenerateIn(
            description="验证一个没有探索产物的场景",
            include_exploration_artifacts=True,
        ),
    )

    assert result.source_summary.exploration_artifacts_requested is True
    assert result.source_summary.exploration_artifacts_used is False
