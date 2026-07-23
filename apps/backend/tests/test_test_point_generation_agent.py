import pytest


@pytest.mark.anyio
async def test_test_point_agent_recovers_from_invalid_structured_tool_call() -> None:
    from typing import Any

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from typing_extensions import override

    from app.agents.test_point_generation.agent import test_point_generation_agent

    class RecordingFakeModel(FakeMessagesListChatModel):
        requests: list[list[BaseMessage]] = []

        @override
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

        @override
        def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
            self.requests.append(messages)
            return super()._generate(messages, *args, **kwargs)

    invalid_id = "call-invalid-test-point-json"
    valid_result = {
        "points": [{"module": "对话模型配置弹窗", "test_point": "支持思考模式的模型显示开关", "priority": "P0"}]
    }
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "id": invalid_id,
                        "name": "TestPointGenerationDraftResult",
                        "args": '{"points": [',
                        "error": "invalid JSON",
                        "type": "invalid_tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-valid-test-point-json",
                        "name": "TestPointGenerationDraftResult",
                        "args": valid_result,
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )

    agent = test_point_generation_agent(model, load_references=False)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "generate"}]})

    assert result["structured_response"].model_dump() == valid_result
    assert len(model.requests) == 2
    recovery_messages = [message for message in model.requests[1] if isinstance(message, ToolMessage)]
    assert len(recovery_messages) == 1
    assert recovery_messages[0].tool_call_id == invalid_id
    assert recovery_messages[0].status == "error"


@pytest.mark.anyio
async def test_test_point_agent_acknowledges_all_calls_before_retry() -> None:
    from langchain_core.messages import AIMessage

    from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware

    assistant_message = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call-valid-but-incomplete-turn",
                "name": "TestPointGenerationResult",
                "args": {},
                "type": "tool_call",
            }
        ],
        invalid_tool_calls=[
            {
                "id": "call-invalid-json",
                "name": "TestPointGenerationResult",
                "args": '{"points": [',
                "error": "invalid JSON",
                "type": "invalid_tool_call",
            }
        ],
    )

    update = InvalidToolCallRecoveryMiddleware().after_model(
        {"messages": [assistant_message]},
        runtime=None,
    )

    assert update is not None
    assert update["jump_to"] == "model"
    assert {message.tool_call_id for message in update["messages"]} == {
        "call-valid-but-incomplete-turn",
        "call-invalid-json",
    }
    assert all(message.status == "error" for message in update["messages"])
