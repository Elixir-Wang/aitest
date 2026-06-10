from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.agents.knowledge_chat.agent import knowledge_chat_agent
from app.agents.knowledge_chat.schemas import KnowledgeQueryInput, KnowledgeQueryOutput
from app.agents.model_selection import build_agent_model, resolve_model_selection


CAPABILITY_ID = "knowledge_query"
SearchProjectKnowledge = Callable[[str], Awaitable[KnowledgeQueryOutput]]


async def run_knowledge_chat(
    input_data: KnowledgeQueryInput,
    search_project_knowledge: SearchProjectKnowledge,
) -> KnowledgeQueryOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    last_tool_output: KnowledgeQueryOutput | None = None

    async def search_project_knowledge_tool(question: str) -> str:
        """查询当前项目最终需求文档和探索记录，并返回带来源引用的项目知识库答案。"""

        nonlocal last_tool_output
        output = await search_project_knowledge(question)
        last_tool_output = output
        return output.model_dump_json()

    search_project_knowledge_tool.__name__ = "search_project_knowledge"
    agent = knowledge_chat_agent(model, [search_project_knowledge_tool])
    return await _invoke_agent(agent, _agent_payload(input_data), last_tool_output)


async def stream_knowledge_chat(
    input_data: KnowledgeQueryInput,
    search_project_knowledge: SearchProjectKnowledge,
) -> AsyncIterator[dict[str, Any]]:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    last_tool_output: KnowledgeQueryOutput | None = None

    async def search_project_knowledge_tool(question: str) -> str:
        """查询当前项目最终需求文档和探索记录，并返回带来源引用的项目知识库答案。"""

        nonlocal last_tool_output
        output = await search_project_knowledge(question)
        last_tool_output = output
        return output.model_dump_json()

    search_project_knowledge_tool.__name__ = "search_project_knowledge"
    agent = knowledge_chat_agent(model, [search_project_knowledge_tool], structured_output=False)
    payload = _agent_payload(input_data)

    if not hasattr(agent, "astream"):
        output = await _invoke_agent(agent, payload, last_tool_output)
        if output.answer:
            yield {"type": "message_delta", "delta": output.answer}
        yield {"type": "metadata", "output": output}
        yield {"type": "done"}
        return

    output: KnowledgeQueryOutput | None = None
    streamed_answer = ""
    structured_json_buffer = ""
    try:
        async for chunk in agent.astream(payload, stream_mode=["messages", "values"]):
            mode, data = _stream_chunk_parts(chunk)
            if mode == "messages":
                delta = _message_delta(data)
                if delta:
                    if structured_json_buffer or _looks_like_structured_output_delta(delta):
                        structured_json_buffer += delta
                        continue
                    streamed_answer += delta
                    yield {"type": "message_delta", "delta": delta}
            elif mode == "values":
                output = _stream_output_from_result(data, last_tool_output, streamed_answer)
    except Exception:
        if not streamed_answer:
            raise
        output = KnowledgeQueryOutput(answer=streamed_answer, knowledge_queried=last_tool_output is not None)
        output = _merge_tool_output(output, last_tool_output)

    if streamed_answer:
        output = _output_from_streamed_answer(streamed_answer, last_tool_output)
    if output is None:
        output = _output_from_structured_json_text(structured_json_buffer, last_tool_output)
    if output is None:
        output = _output_from_streamed_answer(streamed_answer, last_tool_output)
    if not streamed_answer and output.answer:
        yield {"type": "message_delta", "delta": output.answer}
    yield {"type": "metadata", "output": output}
    yield {"type": "done"}


def _agent_payload(input_data: KnowledgeQueryInput) -> dict[str, Any]:
    return {
        "messages": [
            {
                "role": "user",
                "content": _build_chat_input(input_data),
            }
        ]
    }


async def _invoke_agent(agent, payload: dict[str, Any], tool_output: KnowledgeQueryOutput | None) -> KnowledgeQueryOutput:
    result = await agent.ainvoke(payload)
    return _structured_output_from_result(result, tool_output)


def _structured_output_from_result(result: Any, tool_output: KnowledgeQueryOutput | None) -> KnowledgeQueryOutput:
    if not isinstance(result, dict):
        raise ValueError("项目知识库聊天智能体输出格式不正确。")
    output = result.get("structured_response")
    if output is None:
        fallback = _output_from_final_message(result, tool_output)
        if fallback is not None:
            return fallback
        raise ValueError("项目知识库聊天智能体未返回结构化结果。")
    if isinstance(output, KnowledgeQueryOutput):
        return _merge_tool_output(output, tool_output)
    if isinstance(output, dict):
        return _merge_tool_output(KnowledgeQueryOutput.model_validate(output), tool_output)
    if isinstance(output, str):
        return _merge_tool_output(KnowledgeQueryOutput.model_validate_json(output), tool_output)
    raise ValueError("项目知识库聊天智能体输出格式不正确。")


def _stream_output_from_result(
    result: Any,
    tool_output: KnowledgeQueryOutput | None,
    streamed_answer: str,
) -> KnowledgeQueryOutput | None:
    if isinstance(result, dict):
        structured_response = result.get("structured_response")
        if structured_response is not None:
            return _structured_output_from_result(result, tool_output)
        if streamed_answer:
            return _output_from_streamed_answer(streamed_answer, tool_output)
        final_message_output = _output_from_final_message(result, tool_output)
        if final_message_output is not None:
            return final_message_output
    if streamed_answer:
        return _output_from_streamed_answer(streamed_answer, tool_output)
    if tool_output is not None:
        return _merge_tool_output(tool_output, tool_output)
    return None


def _output_from_streamed_answer(
    streamed_answer: str,
    tool_output: KnowledgeQueryOutput | None,
) -> KnowledgeQueryOutput:
    answer = streamed_answer.strip()
    if not answer and tool_output is not None:
        return _merge_tool_output(tool_output, tool_output)
    return _merge_tool_output(
        KnowledgeQueryOutput(answer=answer, knowledge_queried=tool_output is not None),
        tool_output,
    )


def _output_from_final_message(
    result: dict[str, Any],
    tool_output: KnowledgeQueryOutput | None,
) -> KnowledgeQueryOutput | None:
    if tool_output is not None:
        return _merge_tool_output(tool_output, tool_output)
    messages = result.get("messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        answer = _message_delta(message).strip()
        if answer:
            structured_output = _output_from_structured_json_text(answer, tool_output)
            if structured_output is not None:
                return structured_output
            return KnowledgeQueryOutput(answer=answer, knowledge_queried=False)
    return None


def _output_from_structured_json_text(
    text: str,
    tool_output: KnowledgeQueryOutput | None,
) -> KnowledgeQueryOutput | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        return _merge_tool_output(KnowledgeQueryOutput.model_validate_json(stripped), tool_output)
    except Exception:
        return None


def _stream_chunk_parts(chunk: Any) -> tuple[str | None, Any]:
    if isinstance(chunk, tuple):
        if len(chunk) == 2 and isinstance(chunk[0], str):
            return chunk[0], chunk[1]
        if len(chunk) == 3 and isinstance(chunk[1], str):
            return chunk[1], chunk[2]
    return None, chunk


def _message_delta(data: Any) -> str:
    message = data[0] if isinstance(data, tuple) and data else data
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _looks_like_structured_output_delta(delta: str) -> bool:
    stripped = delta.lstrip()
    return stripped.startswith("{") or stripped.startswith(
        (
            '"answer"',
            '"knowledge_queried"',
            '"source_refs"',
            '"used_requirement_versions"',
            '"used_exploration_runs"',
        )
    )


def _merge_tool_output(output: KnowledgeQueryOutput, tool_output: KnowledgeQueryOutput | None) -> KnowledgeQueryOutput:
    if tool_output is None:
        return output
    output.knowledge_queried = True
    if not output.source_refs:
        output.source_refs = tool_output.source_refs
    if not output.used_requirement_versions:
        output.used_requirement_versions = tool_output.used_requirement_versions
    if not output.used_exploration_runs:
        output.used_exploration_runs = tool_output.used_exploration_runs
    return output


def _build_chat_input(input_data: KnowledgeQueryInput) -> str:
    return "\n".join(
        [
            f"项目：{input_data.project_name} ({input_data.project_id})",
            "",
            "最近对话上下文：",
            _format_conversation_history(input_data),
            "",
            "用户问题：",
            input_data.question.strip(),
        ]
    )


def _format_conversation_history(input_data: KnowledgeQueryInput) -> str:
    if not input_data.conversation_history:
        return "无。"
    lines: list[str] = []
    for message in input_data.conversation_history:
        role = "用户" if message.role == "user" else "项目知识库 AI"
        content = message.content.strip()
        if len(content) > 1200:
            content = f"{content[:1200]}..."
        lines.append(f"{role}：{content}")
    return "\n".join(lines)
