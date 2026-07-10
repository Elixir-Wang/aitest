import inspect
import json
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from app.agents.api_automation.agent import api_automation_generation_agent
from app.agents.api_automation.schemas import ApiAutomationGenerationInput, ApiAutomationGenerationResult
from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.core.logging import agent_logger


CAPABILITY_ID = "api_test_generation"
MAX_DEBUG_TEXT_CHARS = 8000


class _ApiAutomationGenerationDebugCallback(BaseCallbackHandler):
    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        **kwargs: Any,
    ) -> None:
        message_summary = [
            [
                {
                    "type": message.__class__.__name__,
                    "content_preview": _trim_debug_text(getattr(message, "content", "")),
                    "tool_calls": _safe_tool_calls(getattr(message, "tool_calls", [])),
                    "tool_call_id": getattr(message, "tool_call_id", None),
                }
                for message in message_batch
            ]
            for message_batch in messages
        ]
        agent_logger.debug(
            "api_automation_generation_chat_model_start | serialized={} messages={}",
            serialized,
            message_summary,
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        generations_summary = []
        for generation_batch in getattr(response, "generations", []) or []:
            batch_summary = []
            for generation in generation_batch:
                message = getattr(generation, "message", None)
                if message is None:
                    batch_summary.append({"text": _trim_debug_text(getattr(generation, "text", ""))})
                    continue
                batch_summary.append(
                    {
                        "type": message.__class__.__name__,
                        "content": _trim_debug_text(getattr(message, "content", "")),
                        "tool_calls": _safe_tool_calls(getattr(message, "tool_calls", [])),
                        "invalid_tool_calls": _safe_tool_calls(getattr(message, "invalid_tool_calls", [])),
                        "response_metadata": getattr(message, "response_metadata", {}),
                    }
                )
            generations_summary.append(batch_summary)
        agent_logger.debug("api_automation_generation_llm_end | generations={}", generations_summary)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        agent_logger.warning(
            "api_automation_generation_llm_error | error_type={} error={}",
            error.__class__.__name__,
            error,
        )


async def generate_api_test_cases(input_data: ApiAutomationGenerationInput) -> ApiAutomationGenerationResult:
    if not input_data.endpoints:
        raise ValueError("接口列表为空，无法生成接口自动化用例。")

    content_parts = [
        f"项目ID: {input_data.project_id}",
        "",
        "接口定义（来自 OpenAPI/手工维护，是接口事实来源）:",
        json.dumps(input_data.endpoints, ensure_ascii=False, indent=2),
    ]

    if input_data.environment_summary:
        content_parts.extend(
            [
                "",
                "接口环境摘要（只用于生成可执行请求，不得输出敏感明文）:",
                json.dumps(input_data.environment_summary, ensure_ascii=False, indent=2),
            ]
        )

    if input_data.source_test_cases:
        content_parts.extend(
            [
                "",
                "可参考的需求测试用例或历史用例:",
                json.dumps(input_data.source_test_cases, ensure_ascii=False, indent=2),
            ]
        )

    if input_data.generation_goal:
        content_parts.extend(["", f"生成目标: {input_data.generation_goal}"])

    content_parts.extend(
        [
            "",
            f"是否生成安全类用例: {input_data.include_security_cases}",
            "",
            "请依据系统提示中的 api-automation-case-generation 规则生成接口自动化用例。",
        ]
    )

    selection = resolve_model_selection(CAPABILITY_ID)
    extra_body = thinking_disabled_extra_body(selection)
    agent_logger.info(
        "api_automation_generation_start | project_id={} endpoint_count={} source_case_count={} "
        "has_environment={} provider={} model={} base_url={} extra_body={}",
        input_data.project_id,
        len(input_data.endpoints),
        len(input_data.source_test_cases),
        bool(input_data.environment_summary),
        selection.provider,
        selection.model,
        selection.base_url,
        extra_body,
    )
    model = build_agent_model(selection, extra_body=extra_body)
    agent = api_automation_generation_agent(model)

    result = await _ainvoke_agent_with_debug_callbacks(
        agent,
        {"messages": [{"role": "user", "content": "\n".join(content_parts)}]},
    )
    agent_logger.info(
        "api_automation_generation_agent_result | keys={} has_structured_response={}",
        sorted(result.keys()) if isinstance(result, dict) else type(result).__name__,
        isinstance(result, dict) and bool(result.get("structured_response")),
    )
    if not isinstance(result, dict):
        raise ValueError("接口自动化用例生成智能体输出格式不正确。")

    generation_result = result.get("structured_response")
    if not generation_result:
        raise ValueError("接口自动化用例生成智能体未返回结构化结果。")

    if isinstance(generation_result, ApiAutomationGenerationResult):
        return generation_result
    if isinstance(generation_result, dict):
        return ApiAutomationGenerationResult.model_validate(generation_result)
    if isinstance(generation_result, str):
        return ApiAutomationGenerationResult.model_validate_json(generation_result)
    raise ValueError(f"接口自动化用例生成智能体输出类型不支持: {type(generation_result).__name__}")


def _trim_debug_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except TypeError:
            value = str(value)
    if len(value) <= MAX_DEBUG_TEXT_CHARS:
        return value
    return f"{value[:MAX_DEBUG_TEXT_CHARS]}...<truncated {len(value) - MAX_DEBUG_TEXT_CHARS} chars>"


async def _ainvoke_agent_with_debug_callbacks(agent: Any, payload: dict[str, Any]) -> Any:
    parameters = inspect.signature(agent.ainvoke).parameters
    if "config" not in parameters:
        return await agent.ainvoke(payload)
    return await agent.ainvoke(
        payload,
        config={"callbacks": [_ApiAutomationGenerationDebugCallback()]},
    )


def _safe_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    safe_calls = []
    if not tool_calls:
        return safe_calls
    for tool_call in tool_calls:
        if isinstance(tool_call, dict):
            safe_calls.append(
                {
                    "id": tool_call.get("id"),
                    "name": tool_call.get("name"),
                    "args": _trim_debug_text(tool_call.get("args")),
                    "type": tool_call.get("type"),
                    "error": _trim_debug_text(tool_call.get("error")),
                }
            )
            continue
        safe_calls.append({"repr": _trim_debug_text(repr(tool_call))})
    return safe_calls
