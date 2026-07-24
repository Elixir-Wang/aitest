import pytest

from app.agents.model_selection import ModelSelection
from app.agents.test_case_generation.schemas import TestCaseGenerationInput, TestCaseGenerationResult


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


@pytest.mark.anyio
async def test_test_case_generation_disables_thinking_for_tool_strategy_models(monkeypatch) -> None:
    from app.agents.test_case_generation import service

    expected = TestCaseGenerationResult(summary="已生成测试用例。", total_count=0, modules=[])
    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            user_content = payload["messages"][0]["content"]
            assert "结合公司测试规范" not in user_content
            assert "include_company_knowledge" not in user_content
            assert "探索产物" not in user_content
            return {"structured_response": expected}

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-chat"),
    )
    monkeypatch.setattr(service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(service, "test_case_generation_agent", lambda model: FakeAgent())

    result = await service.generate_test_cases(
        TestCaseGenerationInput(
            requirement_name="登录需求",
            requirement_content="# 最终需求\n\n用户可以登录。",
        )
    )

    assert result is expected
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}


@pytest.mark.anyio
async def test_test_case_generation_batches_test_points_by_module(monkeypatch) -> None:
    from app.agents.test_case_generation import service

    calls: list[str] = []

    class FakeAgent:
        def __init__(self, batch_id: int):
            self.batch_id = batch_id

        async def ainvoke(self, payload):
            content = payload["messages"][0]["content"]
            calls.append(content)
            module = "模块B" if "模块=模块B" in content else "模块A"
            return {
                "structured_response": {
                    "summary": f"批次 {self.batch_id}",
                    "total_count": 1,
                    "modules": [
                        {
                            "module_name": module,
                            "test_cases": [
                                {
                                    "id": "tc-001",
                                    "module": module,
                                    "title": f"批次 {self.batch_id} 用例",
                                    "priority": "P0",
                                    "type": "功能测试",
                                    "steps": [
                                        {
                                            "action": "执行本批次操作",
                                            "expected_result": "本批次结果正确。",
                                        }
                                    ],
                                    "expected_result": "本批次结果正确。",
                                }
                            ],
                        }
                    ],
                }
            }

    def fake_agent(_model):
        return FakeAgent(len(calls) + 1)

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-chat"),
    )
    monkeypatch.setattr(service, "build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr(service, "test_case_generation_agent", fake_agent)

    test_points = [
        {
            "point_key": f"tp-{index:03d}",
            "title": f"测试点 {index}",
            "module": "模块A" if index <= 6 else "模块B",
            "category": "功能",
            "priority": "P0",
            "description": f"验证测试点 {index}",
            "verification_points": [],
        }
        for index in range(1, 13)
    ]

    result = await service.generate_test_cases(
        TestCaseGenerationInput(
            requirement_name="批量需求",
            requirement_content="# 最终需求\n\n验证批量生成。",
            test_points=test_points,
        )
    )

    assert len(calls) == 4
    assert all(content.count("   描述:") <= service.TEST_POINT_BATCH_SIZE for content in calls)
    assert all("仅生成下列本批次测试点对应的用例" in content for content in calls)
    assert result.total_count == 4
    assert [len(module.test_cases) for module in result.modules] == [2, 2]
    assert [
        test_case.id
        for module in result.modules
        for test_case in module.test_cases
    ] == ["tc-001", "tc-002", "tc-003", "tc-004"]


@pytest.mark.anyio
async def test_generation_retries_only_batch_that_conflicts_with_rejected_reference(monkeypatch) -> None:
    from app.agents.rejected_case_search.schemas import RejectedCaseReference
    from app.agents.test_case_generation import service
    from app.agents.test_case_generation.conflict import GeneratedCaseConflictResult, GeneratedCaseConflict

    calls = []
    checks = []

    class FakeAgent:
        async def ainvoke(self, payload):
            calls.append(payload["messages"][0]["content"])
            return {
                "structured_response": {
                    "summary": "候选",
                    "total_count": 1,
                    "modules": [{
                        "module_name": "登录",
                        "test_cases": [{
                            "id": "tc-001",
                            "module": "登录",
                            "title": "错误密码登录",
                            "priority": "P1",
                            "type": "异常测试",
                            "steps": [{"action": "输入错误密码", "expected_result": "提示错误"}],
                            "expected_result": "登录失败",
                        }],
                    }],
                }
            }

    async def fake_check(_model, _result, _references):
        checks.append(True)
        if len(checks) == 1:
            return GeneratedCaseConflictResult(
                conflicts=[
                    GeneratedCaseConflict(
                        generated_case_id="tc-001",
                        record_id="rjc-1",
                        conflict_type="duplicate",
                        explanation="与历史不采纳用例重复",
                    )
                ]
            )
        return GeneratedCaseConflictResult()

    monkeypatch.setattr(service, "resolve_model_selection", lambda _capability_id: _model_selection())
    monkeypatch.setattr(service, "build_agent_model", lambda *_args, **_kwargs: "model")
    monkeypatch.setattr(service, "test_case_generation_agent", lambda _model: FakeAgent())
    monkeypatch.setattr(service, "check_generated_case_conflicts", fake_check)

    result = await service.generate_test_cases(
        TestCaseGenerationInput(
            requirement_name="登录需求",
            requirement_content="# 登录",
            test_points=[{"point_key": "TP-1", "title": "错误密码", "module": "登录"}],
            rejected_case_references=[
                RejectedCaseReference(
                    record_id="rjc-1",
                    source_file_id="gkfile-1",
                    source_file_name="登录.md",
                    source_requirement_id="doc-old",
                    matched_test_point_keys=["TP-1"],
                    title="错误密码登录",
                    module="登录",
                    reason_type="重复用例",
                    reason="与已有用例重复",
                    handling="block_duplicate",
                    relevance="high",
                )
            ],
        )
    )

    assert result.total_count == 1
    assert len(calls) == 2
    assert len(checks) == 2
    assert "上一次候选用例仍命中" in calls[1]


@pytest.mark.anyio
async def test_test_case_agent_recovers_from_invalid_structured_tool_call() -> None:
    from typing import Any

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from typing_extensions import override

    from app.agents.test_case_generation.agent import test_case_generation_agent

    class RecordingFakeModel(FakeMessagesListChatModel):
        requests: list[list[BaseMessage]] = []

        @override
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

        @override
        def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
            self.requests.append(messages)
            return super()._generate(messages, *args, **kwargs)

    invalid_id = "call-invalid-test-case-json"
    valid_result = {"summary": "已生成测试用例。", "total_count": 0, "modules": []}
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "id": invalid_id,
                        "name": "TestCaseGenerationResult",
                        "args": '{"summary": "broken", "modules": [',
                        "error": "invalid JSON",
                        "type": "invalid_tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-valid-test-case-json",
                        "name": "TestCaseGenerationResult",
                        "args": valid_result,
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )

    agent = test_case_generation_agent(model, load_references=False)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "generate"}]})

    assert result["structured_response"].model_dump() == valid_result
    assert len(model.requests) == 2
    recovery_messages = [message for message in model.requests[1] if isinstance(message, ToolMessage)]
    assert len(recovery_messages) == 1
    assert recovery_messages[0].tool_call_id == invalid_id
    assert recovery_messages[0].status == "error"


def test_test_case_agent_acknowledges_all_calls_before_retry() -> None:
    from langchain_core.messages import AIMessage

    from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware

    assistant_message = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call-valid-but-incomplete-turn",
                "name": "TestCaseGenerationResult",
                "args": {},
                "type": "tool_call",
            }
        ],
        invalid_tool_calls=[
            {
                "id": "call-invalid-json",
                "name": "TestCaseGenerationResult",
                "args": '{"modules": [',
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
