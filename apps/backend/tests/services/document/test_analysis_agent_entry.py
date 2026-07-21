import pytest

from app.agents.requirement_analysis.schemas import RequirementInput
from app.services.document import analysis


@pytest.mark.anyio
async def test_analyze_requirement_with_agent_does_not_pass_run_id(monkeypatch) -> None:
    input_data = RequirementInput(
        requirement_name="超长文本性能优化",
        requirement_content="# 需求内容",
        auxiliary_docs=[],
    )
    expected_result = object()

    monkeypatch.setattr(analysis, "load_run_input", lambda run_id: input_data)

    async def fake_run_requirement_analysis(received_input):
        assert received_input is input_data
        return expected_result

    monkeypatch.setattr(analysis, "run_requirement_analysis", fake_run_requirement_analysis)

    result = await analysis.analyze_requirement_with_agent("reqrun-001")

    assert result is expected_result
