import json
import logging
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from collections.abc import AsyncIterator
from typing import Any

from app.agents.knowledge.agent import knowledge_agent
from app.agents.knowledge.schemas import KnowledgeQueryInput, KnowledgeQueryOutput, KnowledgeSourceDocumentInput
from app.agents.model_selection import build_agent_model, resolve_model_selection

logger = logging.getLogger(__name__)


CAPABILITY_ID = "knowledge_query"


def _selection_log_value(selection: Any, name: str) -> str:
    return str(getattr(selection, name, ""))


async def run_knowledge_agent(input_data: KnowledgeQueryInput, *, thread_id: str | None = None) -> KnowledgeQueryOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=_thinking_extra_body(selection, show_thinking=False))
    agent = knowledge_agent(model)
    result = await agent.ainvoke(_agent_payload(input_data), config=_thread_config(thread_id))
    return _output_from_result(result)


async def stream_knowledge_agent(
    input_data: KnowledgeQueryInput,
    *,
    show_thinking: bool = False,
    thread_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=_thinking_extra_body(selection, show_thinking=show_thinking))
    agent = knowledge_agent(model)
    payload = _agent_payload(input_data)
    if not hasattr(agent, "astream"):
        output = await run_knowledge_agent(input_data, thread_id=thread_id)
        if output.answer:
            yield {"type": "message_delta", "delta": output.answer}
        yield {"type": "metadata", "output": output}
        yield {"type": "done"}
        return

    output: KnowledgeQueryOutput | None = None
    streamed_answer = ""
    used_tools = False
    saw_reasoning = False
    visible_filter = ThinkBlockFilter()
    try:
        async for chunk in agent.astream(payload, config=_thread_config(thread_id), stream_mode=["messages", "values"]):
            mode, data = _stream_chunk_parts(chunk)
            if mode == "messages":
                message = _message_from_stream_data(data)
                if _is_tool_message(message) or _message_tool_calls(message):
                    used_tools = True
                    continue
                reasoning_delta = _message_reasoning_delta(data)
                reasoning_from_content = False
                if show_thinking and not reasoning_delta:
                    reasoning_delta = _message_thinking_blocks(message)
                    reasoning_from_content = bool(reasoning_delta)
                if show_thinking and reasoning_delta:
                    if not saw_reasoning:
                        saw_reasoning = True
                        logger.info(
                            "[knowledge-query] reasoning-started provider=%s model=%s conversation_id=%s",
                            _selection_log_value(selection, "provider"),
                            _selection_log_value(selection, "model"),
                            thread_id or "",
                        )
                    delta = sanitize_visible_thinking(reasoning_delta)
                    if delta:
                        yield {"type": "thinking_delta", "delta": delta}
                    if not reasoning_from_content:
                        continue
                if not _is_ai_message(message):
                    continue
                delta = _message_content(message)
                if show_thinking and reasoning_from_content:
                    delta = _strip_think_blocks(delta)
                    delta = re.sub(r"<\s*/?\s*(?:think|thinking)\s*>", "", delta, flags=re.IGNORECASE | re.DOTALL)
                if not delta or _looks_like_structured_json_delta(delta):
                    continue
                delta = visible_filter.feed(delta)
                if not streamed_answer:
                    delta = delta.lstrip()
                if not delta:
                    continue
                streamed_answer += delta
                yield {"type": "message_delta", "delta": delta}
            elif mode == "values":
                candidate = _output_from_result_if_available(data)
                if candidate is not None:
                    output = candidate
    except Exception:
        if not streamed_answer:
            raise
        output = KnowledgeQueryOutput(answer=streamed_answer.strip(), knowledge_queried=used_tools)

    if output is None:
        if used_tools:
            raise ValueError("知识库 agent 已调用工具但未返回结构化结果。")
        output = KnowledgeQueryOutput(answer=streamed_answer.strip(), knowledge_queried=False)
    if show_thinking and not saw_reasoning:
        logger.info(
            "[knowledge-query] reasoning-missing provider=%s model=%s conversation_id=%s",
            _selection_log_value(selection, "provider"),
            _selection_log_value(selection, "model"),
            thread_id or "",
        )
    output.answer = sanitize_visible_answer(output.answer)
    if not streamed_answer and output.answer:
        yield {"type": "message_delta", "delta": output.answer}
    yield {"type": "metadata", "output": output}
    yield {"type": "done"}


def _agent_payload(input_data: KnowledgeQueryInput) -> dict[str, Any]:
    files = _virtual_files(input_data)
    return {
        "messages": [
            {
                "role": "user",
                "content": "\n".join(
                    [
                        "用户问题：",
                        input_data.question.strip(),
                        "",
                        "可搜索文件：",
                        "\n".join(f"- {path}" for path in sorted(files)) or "无。",
                        "",
                        "说明：以上路径是 Deep Agents StateBackend 虚拟绝对路径，必须按清单原样使用；每个 Markdown 文件顶部都有 JSON 元数据注释，可用于核对来源。",
                    ]
                ),
            }
        ],
        "files": files,
    }


def _thread_config(thread_id: str | None) -> dict[str, Any] | None:
    if not thread_id:
        return None
    return {"configurable": {"thread_id": thread_id}}


def _thinking_extra_body(selection, *, show_thinking: bool) -> dict[str, Any] | None:
    if show_thinking:
        return None
    if not _supports_thinking_toggle(selection):
        return None
    return {"thinking": {"type": "disabled"}}


def _supports_thinking_toggle(selection: Any) -> bool:
    provider = str(getattr(selection, "provider", "")).strip().lower()
    model = str(getattr(selection, "model", "")).strip().lower()
    return "minimax" in provider or "minimax" in model or "deepseek" in provider or "deepseek" in model


def _virtual_files(input_data: KnowledgeQueryInput) -> dict[str, dict[str, str]]:
    files: dict[str, dict[str, str]] = {
        "/README.md": _file_data(_manifest(input_data)),
    }
    for index, document in enumerate(input_data.source_documents, start=1):
        path = _document_path(index, document)
        metadata = _document_metadata(document)
        content = "<!-- source_metadata: " + json.dumps(metadata, ensure_ascii=False) + " -->\n\n" + document.markdown_content
        files[path] = _file_data(content)
    return files


def _file_data(content: str) -> dict[str, str]:
    now = datetime.now(UTC).isoformat()
    return {
        "content": content,
        "encoding": "utf-8",
        "created_at": now,
        "modified_at": now,
    }


def _manifest(input_data: KnowledgeQueryInput) -> str:
    lines = [
        "# 知识库文件清单",
        "",
        "本次查询只能使用这些 Deep Agents StateBackend 虚拟文件作为项目事实和公司知识来源。",
        "所有路径都是虚拟绝对路径，必须按清单原样使用，不得映射为宿主机真实文件路径。",
        "",
        "来源优先级：",
        "1. /requirements/ 下的项目最终需求文档是当前项目业务事实最高依据。",
        "2. /company-knowledge/ 下的公司知识库只提供通用测试方法、平台规范、模板和跨项目经验。",
        "3. 如果两类来源冲突，以项目最终需求为准。",
        "",
    ]
    for index, document in enumerate(input_data.source_documents, start=1):
        lines.append(f"- `{_document_path(index, document)}`: {document.source_title or document.source_id}")
    return "\n".join(lines)


def _document_path(index: int, document: KnowledgeSourceDocumentInput) -> str:
    if document.source_type == "company_knowledge":
        base = _safe_path_part(document.base_name or document.base_id or "company-knowledge")
        folder_parts = [
            _safe_path_part(part)
            for part in (document.folder_path or "").split("/")
            if part.strip()
        ]
        name = _safe_path_part(document.file_name or document.source_title or document.file_id)
        return str(PurePosixPath("/") / "company-knowledge" / base / PurePosixPath(*folder_parts) / f"{index:03d}-{_markdown_name(name)}")
    name = _safe_path_part(document.document_name or document.source_title)
    version = document.version_no if document.version_no is not None else "unknown"
    return str(PurePosixPath("/") / "requirements" / f"{index:03d}-{name}-v{version}.md")


def _markdown_name(name: str) -> str:
    return name if name.lower().endswith(".md") else f"{name}.md"


def _document_metadata(document: KnowledgeSourceDocumentInput) -> dict[str, Any]:
    if document.source_type == "company_knowledge":
        return {
            "source_type": "company_knowledge",
            "source_id": document.source_id or document.file_id,
            "source_title": document.source_title or document.file_name,
            "base_id": document.base_id,
            "base_name": document.base_name,
            "file_id": document.file_id,
            "file_name": document.file_name,
            "folder_path": document.folder_path,
        }
    return {
        "source_type": "requirement",
        "source_id": document.source_id or document.version_id,
        "source_title": document.source_title or f"{document.document_name} v{document.version_no}",
        "project_id": document.project_id,
        "project_name": document.project_name,
        "document_id": document.document_id,
        "document_name": document.document_name,
        "version_id": document.version_id,
        "version_no": document.version_no,
    }


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value.strip())
    cleaned = cleaned.strip(".-")
    return cleaned[:80] or "untitled"


def _output_from_result(result: Any) -> KnowledgeQueryOutput:
    output = _structured_output_from_result(result)
    if output is not None:
        output.answer = sanitize_visible_answer(output.answer)
        return output
    output = _direct_answer_output_from_result(result)
    if output is not None:
        output.answer = sanitize_visible_answer(output.answer)
        return output
    raise ValueError("知识库 agent 未返回结构化结果。")


def _structured_output_from_result(result: Any) -> KnowledgeQueryOutput | None:
    if not isinstance(result, dict):
        return None
    structured = result.get("structured_response")
    if isinstance(structured, KnowledgeQueryOutput):
        return structured
    if isinstance(structured, dict):
        return KnowledgeQueryOutput.model_validate(structured)
    if isinstance(structured, str):
        return KnowledgeQueryOutput.model_validate_json(structured)
    return None


def _output_from_result_if_available(result: Any) -> KnowledgeQueryOutput | None:
    try:
        return _output_from_result(result)
    except Exception:
        return None


def _direct_answer_output_from_result(result: Any) -> KnowledgeQueryOutput | None:
    if not isinstance(result, dict):
        return None
    messages = result.get("messages")
    if not isinstance(messages, list):
        return None
    knowledge_queried = _messages_used_tools(messages)
    for message in reversed(messages):
        if not _is_ai_message(message):
            continue
        content = _message_content(message).strip()
        if content:
            return KnowledgeQueryOutput(answer=content, knowledge_queried=knowledge_queried)
    return None


def _messages_used_tools(messages: list[Any]) -> bool:
    for message in messages:
        if _is_tool_message(message):
            return True
        tool_calls = _message_tool_calls(message)
        if tool_calls:
            return True
    return False


def _is_tool_message(message: Any) -> bool:
    message_type = ""
    if isinstance(message, dict):
        message_type = str(message.get("type") or message.get("role") or "")
    else:
        message_type = str(getattr(message, "type", "") or getattr(message, "role", ""))
    return message_type == "tool" or message.__class__.__name__ == "ToolMessage"


def _message_tool_calls(message: Any) -> Any:
    if isinstance(message, dict):
        return message.get("tool_calls") or message.get("tool_call_chunks")
    return getattr(message, "tool_calls", None) or getattr(message, "tool_call_chunks", None)


def sanitize_visible_thinking(text: str) -> str:
    cleaned = _strip_source_metadata_blocks(text)
    cleaned = re.sub(
        r"^\s*(?:<\!--\s*source_metadata:.*?-->|source_metadata\s*:.*)$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    cleaned = re.sub(r"^\s*(?:read_file|grep|glob|ls)\b.*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\s+(?=\S)", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_source_metadata_blocks(text: str) -> str:
    return re.sub(r"<\!--\s*source_metadata:.*?-->", "", text, flags=re.IGNORECASE | re.DOTALL)


def sanitize_visible_answer(answer: str) -> str:
    cleaned = _strip_think_blocks(answer)
    cleaned = _strip_structured_output_artifacts(cleaned)
    cleaned = re.sub(r"<\s*/?\s*(?:think|thinking)\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _strip_think_blocks(text: str) -> str:
    pattern = re.compile(
        r"<\s*(?:think|thinking)\s*>.*?<\s*/\s*(?:think|thinking)\s*>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    previous = text
    while True:
        current = pattern.sub("", previous)
        if current == previous:
            return current
        previous = current


def _strip_structured_output_artifacts(text: str) -> str:
    cleaned = re.sub(r"<\s*/?\s*KnowledgeQueryOutput\s*>", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<\s*answer\s*>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return re.split(
        r"<\s*/\s*answer\s*>|<\s*used_requirement_versions\b|"
        r"<\s*used_company_knowledge_files\b|<\s*knowledge_queried\b|"
        r"^\s*(?:used_requirement_versions|used_company_knowledge_files|knowledge_queried)\s*:",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )[0]


class ThinkBlockFilter:
    def __init__(self) -> None:
        self._inside = False
        self._pending = ""
        self._discard_structured_tail = False

    def feed(self, text: str) -> str:
        if self._discard_structured_tail:
            return ""
        self._pending += text
        output: list[str] = []
        while self._pending:
            lower = self._pending.lower()
            if self._inside:
                close_match = re.search(r"<\s*/\s*(?:think|thinking)\s*>", lower)
                if not close_match:
                    self._pending = self._pending[-24:]
                    return "".join(output)
                self._pending = self._pending[close_match.end() :]
                self._inside = False
                continue

            open_match = re.search(r"<\s*(?:think|thinking)\s*>", lower)
            structured_match = _structured_output_tail_match(lower)
            output_wrapper_match = re.search(r"<\s*/?\s*knowledgequeryoutput\s*>", lower)
            answer_open_match = re.search(r"<\s*answer\s*>", lower)
            matches = [
                match
                for match in (open_match, structured_match, output_wrapper_match, answer_open_match)
                if match is not None
            ]
            if not matches:
                keep_length = _safe_visible_prefix_length(self._pending)
                output.append(self._pending[:keep_length])
                self._pending = self._pending[keep_length:]
                return "".join(output)
            first_match = min(matches, key=lambda match: match.start())
            if first_match == answer_open_match:
                output.append(self._pending[: first_match.start()])
                self._pending = self._pending[first_match.end() :]
                continue
            if first_match == output_wrapper_match:
                output.append(self._pending[: first_match.start()])
                self._pending = self._pending[first_match.end() :]
                continue
            if first_match == structured_match:
                output.append(self._pending[: first_match.start()])
                self._pending = ""
                self._discard_structured_tail = True
                return "".join(output)
            output.append(self._pending[: open_match.start()])
            self._pending = self._pending[open_match.end() :]
            self._inside = True
        return "".join(output)


def _safe_visible_prefix_length(text: str) -> int:
    max_suffix = min(len(text), 24)
    lower = text.lower()
    structured_prefixes = (
        "</answer",
        "<used_requirement_versions",
        "<used_company_knowledge_files",
        "<knowledge_queried",
        "<knowledgequeryoutput",
        "</knowledgequeryoutput",
        "used_requirement_versions:",
        "used_company_knowledge_files:",
        "knowledge_queried:",
    )
    for suffix_length in range(max_suffix, 0, -1):
        suffix = lower[-suffix_length:]
        if (
            "<think".startswith(suffix)
            or "<thinking".startswith(suffix)
            or "</think".startswith(suffix)
            or "</thinking".startswith(suffix)
            or "<answer".startswith(suffix)
            or any(prefix.startswith(suffix) for prefix in structured_prefixes)
        ):
            return len(text) - suffix_length
    return len(text)


def _structured_output_tail_match(text: str) -> re.Match[str] | None:
    return re.search(
        r"<\s*/\s*answer\s*>|<\s*used_requirement_versions\b|"
        r"<\s*used_company_knowledge_files\b|<\s*knowledge_queried\b|"
        r"^\s*(?:used_requirement_versions|used_company_knowledge_files|knowledge_queried)\s*:",
        text,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )


def _stream_chunk_parts(chunk: Any) -> tuple[str | None, Any]:
    if isinstance(chunk, tuple):
        if len(chunk) == 2 and isinstance(chunk[0], str):
            return chunk[0], chunk[1]
        if len(chunk) == 3 and isinstance(chunk[1], str):
            return chunk[1], chunk[2]
    return None, chunk


def _message_from_stream_data(data: Any) -> Any:
    return data[0] if isinstance(data, tuple) and data else data


def _message_reasoning_delta(data: Any) -> str:
    message = _message_from_stream_data(data)
    if not _is_ai_message(message):
        return ""
    if isinstance(message, dict):
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str):
            return reasoning
        additional_kwargs = message.get("additional_kwargs")
    else:
        reasoning = getattr(message, "reasoning_content", "")
        if isinstance(reasoning, str):
            return reasoning
        additional_kwargs = getattr(message, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        reasoning = additional_kwargs.get("reasoning_content")
        if isinstance(reasoning, str):
            return reasoning
    return ""


def _message_thinking_blocks(message: Any) -> str:
    content = _message_content(message)
    if not content:
        return ""
    matches = re.findall(r"<\s*(?:think|thinking)\s*>(.*?)<\s*/\s*(?:think|thinking)\s*>", content, flags=re.IGNORECASE | re.DOTALL)
    if not matches:
        return ""
    return "\n\n".join(part.strip() for part in matches if part.strip())


def _is_ai_message(message: Any) -> bool:
    message_type = ""
    if isinstance(message, dict):
        message_type = str(message.get("type") or message.get("role") or "")
    else:
        message_type = str(getattr(message, "type", "") or getattr(message, "role", ""))
    return message_type in {"ai", "assistant", "AIMessageChunk"} or message.__class__.__name__ in {
        "AIMessage",
        "AIMessageChunk",
    }


def _looks_like_structured_json_delta(delta: str) -> bool:
    stripped = delta.lstrip()
    return stripped.startswith("```json") or stripped.startswith("{") or stripped.startswith(
        (
            '"answer"',
            '"knowledge_queried"',
            '"used_requirement_versions"',
            '"used_company_knowledge_files"',
            "knowledge_queried:",
            "used_requirement_versions:",
            "used_company_knowledge_files:",
        )
    )


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")
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
