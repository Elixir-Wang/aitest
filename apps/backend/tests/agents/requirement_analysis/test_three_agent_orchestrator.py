from datetime import datetime

import pytest

from app.agents.requirement_analysis.clarification.schemas import (
    ClarificationOutput,
    ClarificationSummary,
)
from app.agents.requirement_analysis.schemas import RequirementAnalysisInputV2
from app.agents.requirement_analysis.quality.schemas import (
    ClarityAssessment,
    CompletenessAssessment,
    ConsistencyAssessment,
    QualityAssessmentOutput,
    QualityDecision,
    QualityIssueSummary,
    TestabilityAssessment,
)
from app.agents.requirement_analysis.understanding.schemas import RequirementUnderstandingOutput


@pytest.mark.anyio
async def test_orchestrator_calls_three_agents_in_order(monkeypatch):
    calls: list[str] = []

    async def fake_understanding_agent(model, primary_markdown_content, **kwargs):
        calls.append("understanding")
        return (
            RequirementUnderstandingOutput(
                modules=[],
                dependencies=[],
                risks=[],
                assumptions=[],
                understanding_summary="理解完成",
            ),
            {"explanation_markdown": ""},
        )

    async def fake_quality_agent(model, **kwargs):
        calls.append("quality")
        assert "understanding_brief" in kwargs
        assert "requirement_evidence" in kwargs
        assert "understanding_result" not in kwargs
        return QualityAssessmentOutput(
            summary=QualityIssueSummary(
                completeness_issues=0,
                clarity_issues=0,
                testability_issues=0,
                consistency_issues=0,
                total_issues=0,
                by_severity={"blocker": 0, "major": 0, "minor": 0},
                has_blocker=False,
                can_proceed=True,
            ),
            decision=QualityDecision(
                result="approved",
                rationale="无阻塞问题",
                blocking_issues=[],
                recommended_actions=[],
            ),
            completeness=CompletenessAssessment(),
            clarity=ClarityAssessment(),
            testability=TestabilityAssessment(),
            consistency=ConsistencyAssessment(),
            assessment_summary="质量评估完成",
        )

    async def fake_clarification_agent(model, **kwargs):
        calls.append("clarification")
        assert "quality_brief" in kwargs
        assert "evidence_snippets" in kwargs
        assert "understanding_result" not in kwargs
        assert "quality_assessment_result" not in kwargs
        return ClarificationOutput(
            items=[],
            summary=ClarificationSummary(
                total=0,
                by_priority={"P0": 0, "P1": 0, "P2": 0, "P3": 0},
                by_category={},
                by_resolution={
                    "auto_resolved": 0,
                    "has_options": 0,
                    "needs_input": 0,
                    "needs_research": 0,
                },
                test_surfaces_coverage={},
                total_test_cases=0,
                blocking_count=0,
                high_risk_count=0,
                recommended_actions=[],
            ),
            overall_assessment="无待澄清项",
            test_strategy_recommendations=[],
            generated_at=datetime.now().isoformat(),
            model_version="test-driven",
        )

    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: object(),
    )
    monkeypatch.setattr(
        "app.agents.model_selection.build_agent_model",
        lambda model_selection: object(),
    )
    import app.agents.requirement_analysis.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "run_understanding_agent", fake_understanding_agent)
    monkeypatch.setattr(orchestrator, "run_quality_assessment_agent", fake_quality_agent)
    assert not hasattr(orchestrator, "run_questioning_agent")
    monkeypatch.setattr(orchestrator, "run_clarification_agent", fake_clarification_agent)

    result = await orchestrator.run_requirement_analysis(
        RequirementAnalysisInputV2(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            run_id="run-1",
            primary_mapping_id="primary",
            primary_filename="登录需求.md",
            primary_markdown_content="# 登录需求\n\n用户可以验证码登录。",
            auxiliary_documents=[],
        )
    )

    assert calls == ["understanding", "quality", "clarification"]
    assert result.status == "completed"
    assert result.metadata["engine"] == "three_agent_orchestrator"
    assert result.questioning is None
    assert result.metadata["step_timings"].keys() >= {
        "understand",
        "quality",
        "clarify",
        "enhance",
    }


def test_package_import_forwards_to_orchestrator():
    from app.agents.requirement_analysis.orchestrator import run_requirement_analysis as orchestrator_run
    from app.agents.requirement_analysis import run_requirement_analysis as package_run

    assert package_run is not orchestrator_run
    assert package_run.__name__ == orchestrator_run.__name__

