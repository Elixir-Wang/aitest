import pytest


def test_requirement_analysis_input_contract_only_contains_primary_fields():
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    assert set(RequirementAnalysisInput.model_fields) == {
        "project_id",
        "document_id",
        "document_name",
        "run_id",
        "primary_mapping_id",
        "primary_filename",
        "primary_markdown_content",
    }


def test_clarification_item_builds_generic_test_decision_fields():
    from app.agents.requirement_analysis.nodes.clarify_node import _create_clarification_item

    item = _create_clarification_item(
        {
            "id": "TC-1",
            "title": "测试覆盖待确认",
            "issue_type": "confirmation",
            "source": "testability",
            "module_key": "order_create",
            "module_name": "订单创建",
            "gap_type": "concurrency",
            "question": "请确认测试覆盖缺口：需求未说明重复提交或并发提交时是否允许创建多笔订单。",
            "impact": "无法编写订单数量、库存扣减次数和重复请求响应的断言。",
            "severity": "major",
            "current_text": "用户提交订单后生成订单记录并扣减库存。",
        },
        {"found": False, "confidence": "low", "answer": "", "source": ""},
    )

    assert item.clarification_bucket == "blocker"
    assert item.decision_point
    assert item.human_question == item.question
    assert "请确认“" in item.question
    assert "验收标准" not in item.question
    assert "data_consistency" in item.affected_surfaces
    assert "api" in item.affected_surfaces
    assert item.risk_scenario.startswith("Given ")
    assert item.draft_acceptance_tests
    assert len(item.decision_options) >= 2


def test_clarification_filter_rejects_generic_nfr_without_source():
    from app.agents.requirement_analysis.nodes.clarify_node import _is_useful_clarification_question

    assert not _is_useful_clarification_question(
        {
            "question": "缺少 compatibility 需求，需要定义什么指标？",
            "impact": "影响兼容性测试。",
            "source": "completeness",
            "issue_type": "missing",
            "current_text": "",
        }
    )


@pytest.mark.anyio
async def test_requirement_analysis_agent_recovers_from_invalid_structured_tool_call() -> None:
    from typing import Any

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from typing_extensions import override

    from app.agents.requirement_analysis.agent import requirement_analysis_agent
    from app.agents.requirement_analysis.schemas import RequirementAnalysisResult

    class RecordingFakeModel(FakeMessagesListChatModel):
        requests: list[list[BaseMessage]] = []

        @override
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

        @override
        def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
            self.requests.append(messages)
            return super()._generate(messages, *args, **kwargs)

    tool_call_id = "call-invalid-requirement-json"
    valid_result = {
        "understanding": {
            "background": "背景",
            "goals": "目标",
            "users": "用户",
            "scope": "范围",
            "flow": "流程",
            "states": "状态",
            "rules": "规则",
            "ui": "界面",
            "data": "数据",
        },
        "clarifications": [
            {
                "id": "clar-001",
                "priority": "P1",
                "module": "对话流",
                "question": "超长文本的长度上限是多少？",
                "option_a": "限制字符数",
                "option_b": "限制 token 数",
                "source_excerpt": "对话流超长文本性能优化",
                "impact": "影响性能测试边界和验收标准。",
            }
        ],
    }
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "id": tool_call_id,
                        "name": "RequirementAnalysisResult",
                        "args": '{"understanding": {"background": "broken"}',
                        "error": "invalid JSON",
                        "type": "invalid_tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-valid-requirement-json",
                        "name": "RequirementAnalysisResult",
                        "args": valid_result,
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )

    agent = requirement_analysis_agent(model, load_references=False)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "analyze"}]})

    assert result["structured_response"] == RequirementAnalysisResult.model_validate(valid_result)
    assert len(model.requests) == 2
    recovery_messages = [message for message in model.requests[1] if isinstance(message, ToolMessage)]
    assert len(recovery_messages) == 1
    assert recovery_messages[0].tool_call_id == tool_call_id
    assert recovery_messages[0].status == "error"
