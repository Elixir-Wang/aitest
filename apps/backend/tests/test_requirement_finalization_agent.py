import asyncio

from app.agents.model_selection import ModelSelection


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


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

    def fake_resolve_model_selection(capability_id):
        seen["capability_id"] = capability_id
        return _model_selection()

    monkeypatch.setattr(service, "resolve_model_selection", fake_resolve_model_selection)
    monkeypatch.setattr(service, "build_agent_model", lambda selection, *, extra_body=None: "model")
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


def test_requirement_finalization_disables_thinking_for_tool_strategy_models(monkeypatch):
    from app.agents.requirement_finalization import service
    from app.agents.requirement_finalization.schemas import RequirementFinalizationInput

    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {
                "structured_response": {
                    "final_requirement_markdown": "# 最终需求\n",
                    "change_summary": "已生成最终需求",
                }
            }

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="minimax", model="MiniMax-M1"),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
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

    assert result.final_requirement_markdown == "# 最终需求\n"
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}
