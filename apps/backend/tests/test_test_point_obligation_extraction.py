import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.test_point_generation import obligation_service
from app.agents.test_point_generation.schemas import (
    RequirementObligation,
    RequirementObligationExtractionResult,
    TestPointGenerationInput as GenerationInput,
)


def test_obligation_schema_requires_source_and_statement():
    with pytest.raises(ValidationError):
        RequirementObligation(
            obligation_key="REQ-001",
            source_section="",
            statement="",
            obligation_type="business_rule",
        )


def test_extraction_uses_only_final_requirement_content(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["content"] = payload["messages"][0]["content"]
            return {
                "structured_response": RequirementObligationExtractionResult(
                    obligations=[
                        RequirementObligation(
                            obligation_key="REQ-001",
                            source_section="改造方案",
                            statement="超过10000字符时存入数据库",
                            obligation_type="business_rule",
                            thresholds=["10000"],
                        )
                    ],
                    unverifiable_items=[],
                )
            }

    monkeypatch.setattr(
        obligation_service,
        "resolve_model_selection",
        lambda capability_id: SimpleNamespace(provider="test", model="test"),
    )
    monkeypatch.setattr(obligation_service, "build_agent_model", lambda selection, extra_body=None: object())
    monkeypatch.setattr(obligation_service, "requirement_obligation_agent", lambda model: FakeAgent())

    result = asyncio.run(
        obligation_service.extract_requirement_obligations(
            GenerationInput(
                requirement_name="最终需求",
                requirement_content="# 最终需求\n超过10000字符时存入数据库。",
                requirement_version_id="version-1",
            )
        )
    )

    assert "最终需求文档" in captured["content"]
    assert "初始需求" not in captured["content"]
    assert result.obligations[0].obligation_key == "REQ-001"
