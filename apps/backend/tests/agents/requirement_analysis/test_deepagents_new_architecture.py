from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    ClarificationItem,
    RequirementAnalysisResult,
    RequirementInput,
    RequirementUnderstanding,
)
from app.agents.model_selection import ModelSelection


AGENT_ROOT = Path("app/agents/requirement_analysis")


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


def test_requirement_analysis_uses_new_deepagents_layout() -> None:
    assert (AGENT_ROOT / "agent.py").exists()
    assert (AGENT_ROOT / "service.py").exists()
    assert (AGENT_ROOT / "schemas.py").exists()
    assert (AGENT_ROOT / "system_prompt.py").exists()
    assert (AGENT_ROOT / "skills" / "requirements-analysis" / "SKILL.md").exists()
    assert (AGENT_ROOT / "skills" / "requirements-analysis" / "references" / "understanding.md").exists()
    assert (AGENT_ROOT / "skills" / "requirements-analysis" / "references" / "clarification.md").exists()
    assert not (AGENT_ROOT / "orchestrator.py").exists()
    assert not (AGENT_ROOT / "understanding").exists()
    assert not (AGENT_ROOT / "quality").exists()
    assert not (AGENT_ROOT / "clarification").exists()


def test_requirement_analysis_contract_is_minimal() -> None:
    assert set(RequirementInput.model_fields) == {"requirement_name", "requirement_content", "auxiliary_docs"}
    assert set(RequirementAnalysisResult.model_fields) == {"understanding", "clarifications"}


def test_requirement_analysis_requires_clarification_items() -> None:
    with pytest.raises(ValidationError):
        RequirementAnalysisResult(
            understanding=RequirementUnderstanding(
                background="背景",
                goals="目标",
                users="用户",
                scope="范围",
                flow="流程",
                states="状态",
                rules="规则",
                ui="界面",
                data="数据",
            ),
            clarifications=[],
        )


def test_requirement_analysis_agent_uses_deepagents_skills_middleware(monkeypatch) -> None:
    calls = {}

    def fake_create_agent(**kwargs):
        calls["agent_kwargs"] = kwargs
        return "agent"

    monkeypatch.setattr("app.agents.requirement_analysis.agent.create_agent", fake_create_agent)

    agent = requirement_analysis_agent("model")

    assert agent == "agent"
    assert calls["agent_kwargs"]["model"] == "model"
    assert calls["agent_kwargs"]["tools"] == []
    assert calls["agent_kwargs"]["system_prompt"] is None
    assert len(calls["agent_kwargs"]["middleware"]) == 1
    assert calls["agent_kwargs"]["middleware"][0].name == "SkillMiddleware"


@pytest.mark.anyio
async def test_requirement_analysis_service_returns_structured_response(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    expected = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="原文说明用户需要完成登录能力，以便进入系统使用受保护功能。",
            goals="目标是让已注册用户能够通过账号完成身份识别，进入系统后继续办理业务。",
            users="主要用户为已注册用户，使用场景是在访问系统时输入账号凭证并进入工作台。",
            scope="当前范围包含登录入口、凭证提交、系统校验和登录结果反馈。",
            flow="用户打开登录页，输入账号信息并提交，系统校验后返回成功或失败结果。",
            states="原文未说明。",
            rules="原文未说明。",
            ui="原文未说明。",
            data="原文未说明。",
        ),
        clarifications=[
            ClarificationItem(
                id="clar-001",
                priority="P3",
                module="登录",
                question="登录失败次数是否有限制？",
                option_a="限制失败次数并临时锁定",
                option_b="不限制失败次数",
                impact="影响安全规则。",
            )
        ],
    )

    class FakeAgent:
        async def ainvoke(self, payload):
            content = payload["messages"][0]["content"]
            assert "需求名称: 登录需求" in content
            assert "主需求内容:" in content
            assert "辅助文档:" not in content
            return {"structured_response": expected}

    monkeypatch.setattr("app.agents.requirement_analysis.service.resolve_model_selection", lambda capability_id: _model_selection())
    monkeypatch.setattr("app.agents.requirement_analysis.service.build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr("app.agents.requirement_analysis.service.requirement_analysis_agent", lambda model: FakeAgent())

    result = await analyze_requirement(
        RequirementInput(
            requirement_name="登录需求",
            requirement_content="# 登录\n\n用户可以登录。",
        )
    )

    assert result is expected


@pytest.mark.anyio
async def test_requirement_analysis_disables_thinking_for_tool_strategy_models(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    expected = RequirementAnalysisResult(
        understanding=RequirementUnderstanding(
            background="已分析。",
            goals="已分析。",
            users="已分析。",
            scope="已分析。",
            flow="已分析。",
            states="已分析。",
            rules="已分析。",
            ui="已分析。",
            data="已分析。",
        ),
        clarifications=[
            ClarificationItem(  # type: ignore[call-arg]
                id="clar-001",
                priority="P0",
                module="登录",
                question="测试问题？",
                option_a="选项 A",
                option_b="选项 B",
                impact="影响说明。",
            )
        ],
    )
    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {"structured_response": expected}

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["selection"] = selection
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        "app.agents.requirement_analysis.service.resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-reasoner"),
    )
    monkeypatch.setattr("app.agents.requirement_analysis.service.build_agent_model", fake_build_agent_model)
    monkeypatch.setattr("app.agents.requirement_analysis.service.requirement_analysis_agent", lambda model: FakeAgent())

    result = await analyze_requirement(
        RequirementInput(
            requirement_name="登录需求",
            requirement_content="# 登录\n\n用户可以登录。",
        )
    )

    assert result is expected
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.anyio
async def test_requirement_analysis_service_rejects_empty_requirement_content(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    with pytest.raises(ValueError, match="主需求内容为空"):
        await analyze_requirement(
            RequirementInput(
                requirement_name="通用模型网关设计",
                requirement_content="   ",
            )
        )


@pytest.mark.anyio
async def test_requirement_analysis_service_rejects_missing_structured_response(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    class FakeAgent:
        async def ainvoke(self, payload):
            return {}

    monkeypatch.setattr("app.agents.requirement_analysis.service.resolve_model_selection", lambda capability_id: _model_selection())
    monkeypatch.setattr("app.agents.requirement_analysis.service.build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr("app.agents.requirement_analysis.service.requirement_analysis_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await analyze_requirement(
            RequirementInput(
                requirement_name="登录需求",
                requirement_content="# 登录\n\n用户可以登录。",
            )
        )
