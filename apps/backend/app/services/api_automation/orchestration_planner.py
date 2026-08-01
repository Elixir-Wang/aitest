from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from pydantic import ValidationError

from app.agents.api_automation.orchestration.schemas import PlannerProposal


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

    async def plan(self, snapshot: dict[str, Any]) -> PlannerProposal:
        self.model_call_count = 0
        started_at = time.monotonic()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是接口自动化场景规划器。根据输入的候选接口、环境和当前场景，输出一个 JSON 对象。"
                    "你负责接口调用顺序、字段来源、接口依赖、Mock 候选值、提取器和断言建议。"
                    "只能引用输入中存在的 endpoint_id、环境变量、场景变量和响应字段。"
                    "不要输出 Markdown，不要调用工具，不要输出解释。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        last_error = ""
        last_content = ""
        for attempt in range(2):
            remaining = self.total_deadline_seconds - (time.monotonic() - started_at)
            if remaining <= 0:
                raise PlannerTimeoutError("AI 编排任务超过总 deadline。")
            timeout = min(self.request_timeout_seconds, remaining)
            self.model_call_count += 1
            try:
                response = await asyncio.wait_for(self.model.ainvoke(messages), timeout=timeout)
            except TimeoutError as exc:
                raise PlannerTimeoutError("AI 规划请求超时。") from exc
            except Exception as exc:
                raise PlannerProviderError(str(exc)) from exc

            last_content = _response_content(response)
            try:
                return PlannerProposal.model_validate(_parse_json_object(last_content))
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = str(exc)
                if attempt == 1:
                    break
                messages = [
                    *messages,
                    {"role": "assistant", "content": last_content},
                    {
                        "role": "user",
                        "content": (
                            "修复上一条输出。只返回符合 PlannerProposal JSON Schema 的完整 JSON 对象，"
                            f"不要解释。校验错误：{last_error}"
                        ),
                    },
                ]

        raise PlannerProtocolError(f"AI 编排结果修复后仍不符合协议：{last_error}")


def _response_content(response: Any) -> str:
    content = response.get("content") if isinstance(response, dict) else getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts).strip()
    return str(content).strip()


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Planner 输出必须是 JSON 对象。")
    return parsed


__all__ = [
    "ApiScenarioPlanner",
    "PlannerError",
    "PlannerProtocolError",
    "PlannerProviderError",
    "PlannerTimeoutError",
]
