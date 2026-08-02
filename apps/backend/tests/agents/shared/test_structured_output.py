import asyncio
import json

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.agents.shared.structured_output import structured_output_runnable


class _Decision(BaseModel):
    action_type: str
    reason: str = ""


class _BoundModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    async def ainvoke(self, messages):
        self.messages.append(messages)
        return self.responses.pop(0)


class _Model:
    def __init__(self, *, tool_responses=(), text_responses=(), bind_error=None):
        self.bound = _BoundModel(tool_responses)
        self.text = _BoundModel(text_responses)
        self.bind_error = bind_error
        self.bound_tools = None

    def bind_tools(self, tools):
        self.bound_tools = tools
        if self.bind_error:
            raise self.bind_error
        return self.bound

    async def ainvoke(self, messages):
        return await self.text.ainvoke(messages)


def test_structured_output_uses_compact_tool_schema_and_validates_arguments() -> None:
    model = _Model(
        tool_responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "_Decision",
                        "args": {"action_type": "skip", "reason": "covered"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )

    output = structured_output_runnable(model, _Decision)
    result = asyncio.run(output.ainvoke([{"role": "user", "content": "decide"}]))

    assert result == _Decision(action_type="skip", reason="covered")
    assert output.model_call_count == 1
    serialized_tools = json.dumps(model.bound_tools, ensure_ascii=False)
    assert '"title"' not in serialized_tools
    assert '"default"' not in serialized_tools


def test_structured_output_accepts_fenced_json_from_tool_bound_model() -> None:
    model = _Model(
        tool_responses=[
            AIMessage(
                content='```json\n{"action_type":"skip","reason":"already covered"}\n```'
            )
        ]
    )

    result = asyncio.run(structured_output_runnable(model, _Decision).ainvoke([{"role": "user", "content": "decide"}]))

    assert result.action_type == "skip"
    assert model.text.messages == []


def test_structured_output_falls_back_when_tool_binding_is_unsupported() -> None:
    model = _Model(
        bind_error=NotImplementedError("tools unsupported"),
        text_responses=[AIMessage(content='{"action_type":"skip","reason":"fallback"}')],
    )

    result = asyncio.run(structured_output_runnable(model, _Decision).ainvoke([{"role": "user", "content": "decide"}]))

    assert result.reason == "fallback"
    assert len(model.text.messages) == 1


def test_structured_output_retries_invalid_json_once() -> None:
    model = _Model(
        bind_error=NotImplementedError("tools unsupported"),
        text_responses=[
            AIMessage(content="not-json"),
            AIMessage(content='{"action_type":"skip","reason":"corrected"}'),
        ],
    )

    result = asyncio.run(structured_output_runnable(model, _Decision).ainvoke([{"role": "user", "content": "decide"}]))

    assert result.reason == "corrected"
    assert len(model.text.messages) == 2
    assert "上一次输出无法通过结构校验" in model.text.messages[1][-1]["content"]


def test_structured_output_repairs_invalid_tool_response_in_one_fallback_call() -> None:
    model = _Model(
        tool_responses=[AIMessage(content='{"unexpected":true}')],
        text_responses=[AIMessage(content='{"action_type":"skip","reason":"corrected"}')],
    )
    output = structured_output_runnable(model, _Decision)

    result = asyncio.run(output.ainvoke([{"role": "user", "content": "decide"}]))

    assert result.reason == "corrected"
    assert output.model_call_count == 2
    assert len(model.text.messages) == 1
    assert "上一次输出无法通过结构校验" in model.text.messages[0][-1]["content"]
