import asyncio


def test_requirement_finalization_input_excludes_no_op_bucket():
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    assert "no_op_clarifications" not in RequirementFinalizationInput.model_fields


def test_requirement_finalization_reuses_requirement_analysis_model(monkeypatch):
    from app.agents.requirement_finalization import service
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            seen["payload"] = payload
            return {
                "structured_response": {
                    "final_requirement_markdown": "# 最终需求\n",
                    "change_summary": "已生成最终需求",
                }
            }

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: seen.setdefault("capability_id", capability_id))
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "requirement_finalization_agent", lambda model: FakeAgent())

    result = asyncio.run(
        service.run_requirement_finalization(
            RequirementFinalizationInput(
                document_name="需求",
                standard_markdown="# 标准需求\n",
                preliminary_markdown="# 初步需求\n",
                primary_document={"filename": "main.md", "markdown_content": "# 标准需求\n"},
            )
        )
    )

    assert seen["capability_id"] == "requirement_analysis"
    assert result.final_requirement_markdown == "# 最终需求\n"
