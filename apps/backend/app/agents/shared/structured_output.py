from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError


SchemaT = TypeVar("SchemaT", bound=BaseModel)
_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)


class StructuredOutputError(ValueError):
    pass


class StructuredOutputRunnable(Generic[SchemaT]):
    def __init__(self, model: Any, schema: type[SchemaT], *, correction_retries: int = 1):
        self.model = model
        self.schema = schema
        self.correction_retries = correction_retries

    async def ainvoke(self, messages: Any, config: Any = None, **kwargs: Any) -> SchemaT:
        tool_response = await self._invoke_with_tool(messages, config=config, **kwargs)
        if tool_response is not None:
            try:
                return _validate_response(tool_response, self.schema)
            except (StructuredOutputError, ValidationError):
                pass
        return await self._invoke_json_fallback(messages, config=config, **kwargs)

    async def _invoke_with_tool(self, messages: Any, *, config: Any, **kwargs: Any) -> Any | None:
        try:
            tool_model = self.model.bind_tools([_tool_definition(self.schema)])
        except (AttributeError, NotImplementedError):
            return None
        try:
            return await _ainvoke(tool_model, messages, config=config, **kwargs)
        except Exception as exc:
            if _is_unsupported_tool_error(exc):
                return None
            raise

    async def _invoke_json_fallback(self, messages: Any, *, config: Any, **kwargs: Any) -> SchemaT:
        validation_error = ""
        for attempt in range(self.correction_retries + 1):
            prompt = _json_instruction(self.schema, validation_error=validation_error)
            response = await _ainvoke(
                self.model,
                [*messages, {"role": "user", "content": prompt}],
                config=config,
                **kwargs,
            )
            try:
                return _validate_response(response, self.schema)
            except (StructuredOutputError, ValidationError) as exc:
                validation_error = str(exc)[:1000]
                if attempt >= self.correction_retries:
                    raise StructuredOutputError(
                        f"{self.schema.__name__} 输出经过纠错后仍无法通过结构校验: {exc}"
                    ) from exc
        raise StructuredOutputError(f"{self.schema.__name__} 未返回结构化结果")


def structured_output_runnable(
    model: Any,
    schema: type[SchemaT],
    *,
    correction_retries: int = 1,
) -> StructuredOutputRunnable[SchemaT]:
    return StructuredOutputRunnable(model, schema, correction_retries=correction_retries)


async def _ainvoke(target: Any, messages: Any, *, config: Any, **kwargs: Any) -> Any:
    if config is None and not kwargs:
        return await target.ainvoke(messages)
    return await target.ainvoke(messages, config=config, **kwargs)


def _tool_definition(schema: type[BaseModel]) -> dict[str, Any]:
    description = (schema.__doc__ or f"Return a validated {schema.__name__} object.").strip()
    return {
        "type": "function",
        "function": {
            "name": schema.__name__,
            "description": description,
            "parameters": _compact_schema(schema.model_json_schema()),
        },
    }


def _compact_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact_schema(item)
            for key, item in deepcopy(value).items()
            if key not in {"title", "default", "examples"}
        }
    if isinstance(value, list):
        return [_compact_schema(item) for item in value]
    return value


def _validate_response(response: Any, schema: type[SchemaT]) -> SchemaT:
    if isinstance(response, schema):
        return response

    tool_calls = _tool_calls(response)
    if tool_calls:
        arguments = tool_calls[0].get("args") or tool_calls[0].get("arguments")
        if isinstance(arguments, str):
            return schema.model_validate_json(arguments)
        return schema.model_validate(arguments)

    if _is_message_response(response):
        text = _message_text(response)
        if not text:
            raise StructuredOutputError("模型没有返回工具参数或 JSON 文本")
        return schema.model_validate_json(_unwrap_json_fence(text))

    if isinstance(response, BaseModel):
        return schema.model_validate(response.model_dump())
    if isinstance(response, dict):
        return schema.model_validate(response)
    if isinstance(response, str):
        return schema.model_validate_json(_unwrap_json_fence(response))
    raise StructuredOutputError(f"不支持的结构化输出类型: {type(response).__name__}")


def _tool_calls(response: Any) -> list[dict[str, Any]]:
    calls = getattr(response, "tool_calls", None)
    if calls is None and isinstance(response, dict):
        calls = response.get("tool_calls")
    return [call for call in calls or [] if isinstance(call, dict)]


def _is_message_response(response: Any) -> bool:
    return hasattr(response, "content") or (
        isinstance(response, dict) and ("content" in response or "tool_calls" in response)
    )


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response.get("content") if isinstance(response, dict) else response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _unwrap_json_fence(text: str) -> str:
    stripped = text.strip()
    match = _JSON_FENCE.fullmatch(stripped)
    return match.group(1).strip() if match else stripped


def _json_instruction(schema: type[BaseModel], *, validation_error: str) -> str:
    schema_json = json.dumps(_compact_schema(schema.model_json_schema()), ensure_ascii=False, separators=(",", ":"))
    if validation_error:
        prefix = f"上一次输出无法通过结构校验：{validation_error}\n"
    else:
        prefix = "当前模型未返回可用的结构化工具调用。\n"
    return (
        prefix
        + "请严格按照以下 JSON Schema 返回一个 JSON 对象。只返回 JSON，不要使用 Markdown 代码块或解释文本。\n"
        + schema_json
    )


def _is_unsupported_tool_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status_code in {400, 404, 422} and any(
        marker in message for marker in ("tool", "function", "unsupported", "unknown parameter")
    )
