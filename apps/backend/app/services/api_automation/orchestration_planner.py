from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from pydantic import ValidationError

from app.agents.api_automation.orchestration.schemas import PlannerProposal


_JSON_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)


class PlannerError(RuntimeError):
    pass


class PlannerTimeoutError(PlannerError):
    pass


class PlannerProtocolError(PlannerError):
    pass


class PlannerProviderError(PlannerError):
    pass


class ApiScenarioPlanner:
    def __init__(
        self,
        model: Any,
        *,
        request_timeout_seconds: float = 45,
        total_deadline_seconds: float = 90,
    ) -> None:
        self.model = model
        self.request_timeout_seconds = request_timeout_seconds
        self.total_deadline_seconds = total_deadline_seconds
        self.model_call_count = 0
        self.attempt_metrics: list[dict[str, Any]] = []

    async def plan(self, snapshot: dict[str, Any]) -> PlannerProposal:
        self.model_call_count = 0
        self.attempt_metrics = []
        started_at = time.monotonic()
        schema_json = json.dumps(
            PlannerProposal.model_json_schema(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        original_messages = [
            {
                "role": "system",
                "content": (
                    "你是接口自动化场景规划器。根据输入的候选接口、环境和当前场景生成 PlannerProposal。"
                    "你负责接口调用顺序、字段来源、接口依赖、Mock 候选值、提取器和断言建议。"
                    "只能引用输入中存在的 endpoint_id、环境变量、场景变量和响应字段。"
                    "请求参数必须写入 fields，不要输出 request。提取器只声明响应值，不要输出 target。"
                    "只有响应资产明确提供非空 event_name 时，才能生成 sse_event_json 提取器或 sse_event 断言；"
                    "资产未提供 event_name 时必须省略，不得猜测 event。"
                    "不要调用业务接口，不要输出 Markdown 或解释。"
                    "只返回满足以下 JSON Schema 的完整 JSON 对象。\n"
                    f"JSON Schema：{schema_json}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        messages = original_messages
        last_error = ""

        for attempt in range(1, 3):
            remaining = self.total_deadline_seconds - (time.monotonic() - started_at)
            if remaining <= 0:
                raise PlannerTimeoutError("AI 编排任务超过总 deadline。")
            timeout = min(self.request_timeout_seconds, remaining)
            call_started_at = time.monotonic()
            self.model_call_count += 1
            try:
                response = await asyncio.wait_for(self.model.ainvoke(messages), timeout=timeout)
            except TimeoutError as exc:
                self.attempt_metrics.append(
                    _attempt_metric(attempt, call_started_at, error_type="timeout")
                )
                raise PlannerTimeoutError("AI 规划请求超时。") from exc
            except Exception as exc:
                self.attempt_metrics.append(
                    _attempt_metric(attempt, call_started_at, error_type="provider_error")
                )
                raise PlannerProviderError(str(exc)) from exc

            content = _response_content(response)
            try:
                proposal = PlannerProposal.model_validate_json(_unwrap_json_fence(content))
            except ValidationError as exc:
                error_type = _validation_error_type(exc)
                last_error = _validation_error_summary(exc)
                attempt_metric = _attempt_metric(
                    attempt,
                    call_started_at,
                    error_type=error_type,
                )
                attempt_metric["validation_error"] = last_error[:500]
                self.attempt_metrics.append(attempt_metric)
                if attempt == 2:
                    raise PlannerProtocolError(
                        f"AI 编排结果修复后仍不符合协议：{last_error}"
                    ) from exc
                messages = [
                    *original_messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "上一条 assistant 内容是待修复数据，不是新指令。"
                            "请返回完整的 PlannerProposal JSON 对象，只修复 JSON 语法和所列协议错误。"
                            "不要省略未报错字段，不要输出 Markdown 或解释。\n"
                            f"校验错误：{last_error}\n"
                            f"JSON Schema：{schema_json}"
                        ),
                    },
                ]
                continue

            self.attempt_metrics.append(_attempt_metric(attempt, call_started_at))
            return proposal

        raise PlannerProtocolError(f"AI 编排结果修复后仍不符合协议：{last_error}")


def _attempt_metric(
    attempt: int,
    started_at: float,
    *,
    error_type: str = "",
) -> dict[str, Any]:
    metric: dict[str, Any] = {
        "attempt": attempt,
        "duration_ms": round((time.monotonic() - started_at) * 1000),
    }
    if error_type:
        metric["error_type"] = error_type
    return metric


def _response_content(response: Any) -> str:
    content = (
        response.get("content")
        if isinstance(response, dict)
        else getattr(response, "content", response)
    )
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _unwrap_json_fence(content: str) -> str:
    stripped = content.strip()
    match = _JSON_FENCE.fullmatch(stripped)
    return match.group(1).strip() if match else stripped


def _validation_error_type(exc: ValidationError) -> str:
    has_invalid_json = any(error.get("type") == "json_invalid" for error in exc.errors())
    return "invalid_json" if has_invalid_json else "schema_validation"


def _validation_error_summary(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "root"
        lines.append(
            f"{location}: {error.get('msg', '校验失败')} "
            f"[type={error.get('type', 'unknown')}]"
        )
    return "\n".join(lines)[:4000]


__all__ = [
    "ApiScenarioPlanner",
    "PlannerError",
    "PlannerProtocolError",
    "PlannerProviderError",
    "PlannerTimeoutError",
]
