from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    RequirementAnalysisAgentInput,
    RequirementAnalysisAgentOutput,
    RequirementAnalysisRunInput,
)


AGENT_ROOT = Path("app/agents/requirement_analysis")


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
    assert set(RequirementAnalysisRunInput.model_fields) == {"run_id"}
    assert set(RequirementAnalysisAgentOutput.model_fields) == {
        "status",
        "understanding_markdown",
        "clarification_markdown",
        "clarification_items",
    }


def test_requirement_analysis_status_matches_clarification_items() -> None:
    RequirementAnalysisAgentOutput(
        status="completed",
        understanding_markdown="## 需求理解\n原文未说明",
        clarification_markdown="## 待澄清内容\n暂无",
        clarification_items=[],
    )

    RequirementAnalysisAgentOutput(
        status="needs_clarification",
        understanding_markdown="## 需求理解\n原文未说明",
        clarification_markdown="## 待澄清内容\n| 优先级 | 模块/对象 | 澄清问题 | 影响 |\n|---|---|---|---|",
        clarification_items=[
            {
                "id": "clar-001",
                "priority": "P0",
                "module": "登录",
                "question": "账号冻结时是否允许登录？",
                "impact": "影响权限规则实现。",
            }
        ],
    )

    with pytest.raises(ValidationError):
        RequirementAnalysisAgentOutput(
            status="completed",
            understanding_markdown="## 需求理解\n原文未说明",
            clarification_markdown="## 待澄清内容\n| 优先级 | 模块/对象 | 澄清问题 | 影响 |\n|---|---|---|---|",
            clarification_items=[
                {
                    "id": "clar-001",
                    "priority": "P0",
                    "module": "登录",
                    "question": "账号冻结时是否允许登录？",
                    "impact": "影响权限规则实现。",
                }
            ],
        )


def test_requirement_analysis_agent_uses_deepagents_skills_middleware(monkeypatch) -> None:
    calls = {}

    class FakeBackend:
        def __init__(self, **kwargs):
            calls["backend_kwargs"] = kwargs

    class FakeSkillsMiddleware:
        def __init__(self, **kwargs):
            calls["skills_kwargs"] = kwargs

    def fake_create_deep_agent(**kwargs):
        calls["agent_kwargs"] = kwargs
        return "agent"

    monkeypatch.setattr("deepagents.create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr("deepagents.backends.filesystem.FilesystemBackend", FakeBackend)
    monkeypatch.setattr("deepagents.middleware.skills.SkillsMiddleware", FakeSkillsMiddleware)

    agent = requirement_analysis_agent("model")

    assert agent == "agent"
    assert calls["agent_kwargs"]["model"] == "model"
    assert calls["agent_kwargs"]["tools"] == []
    assert "subagents" not in calls["agent_kwargs"]
    assert calls["skills_kwargs"]["sources"] == [
        ("/app/agents/requirement_analysis/skills", "RequirementAnalysis")
    ]
    assert calls["agent_kwargs"]["middleware"]
    assert "需求分析智能体" in calls["agent_kwargs"]["system_prompt"]
    assert "requirements-analysis" in calls["agent_kwargs"]["system_prompt"]


@pytest.mark.anyio
async def test_requirement_analysis_service_returns_structured_response(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    expected = RequirementAnalysisAgentOutput(
        status="completed",
        understanding_markdown="## 需求理解\n\n### 1. 需求背景\n原文未说明",
        clarification_markdown="## 待澄清内容\n\n暂无。",
        clarification_items=[],
    )

    class FakeAgent:
        async def ainvoke(self, payload):
            content = payload["messages"][0]["content"]
            assert "需求名称: 登录需求" in content
            assert "主需求 Markdown:" in content
            assert "辅助需求 Markdown 列表:" in content
            return {"structured_response": expected}

    monkeypatch.setattr("app.agents.requirement_analysis.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.requirement_analysis.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.requirement_analysis.service.requirement_analysis_agent", lambda model: FakeAgent())

    result = await analyze_requirement(
        RequirementAnalysisAgentInput(
            requirement_name="登录需求",
            primary_filename="login.md",
            primary_markdown_content="# 登录\n\n用户可以登录。",
        )
    )

    assert result is expected


@pytest.mark.anyio
async def test_requirement_analysis_service_rejects_missing_structured_response(monkeypatch) -> None:
    from app.agents.requirement_analysis.service import analyze_requirement

    class FakeAgent:
        async def ainvoke(self, payload):
            return {}

    monkeypatch.setattr("app.agents.requirement_analysis.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.requirement_analysis.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.requirement_analysis.service.requirement_analysis_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await analyze_requirement(
            RequirementAnalysisAgentInput(
                requirement_name="登录需求",
                primary_filename="login.md",
                primary_markdown_content="# 登录\n\n用户可以登录。",
            )
        )
