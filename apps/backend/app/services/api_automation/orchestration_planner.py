from __future__ import annotations

import asyncio
import json
from typing import Any

from app.agents.api_automation.orchestration.schemas import PlannerProposal
from app.agents.shared.structured_output import StructuredOutputError, structured_output_runnable


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
        total_deadline_seconds: float = 90,
    ) -> None:
        self.model = model
        self.total_deadline_seconds = total_deadline_seconds
        self.model_call_count = 0

    async def plan(self, snapshot: dict[str, Any]) -> PlannerProposal:
        self.model_call_count = 0
        messages = [
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
                ),
            },
            {
                "role": "user",
                "content": json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            },
        ]
        output = structured_output_runnable(self.model, PlannerProposal, correction_retries=1)
        try:
            return await asyncio.wait_for(output.ainvoke(messages), timeout=self.total_deadline_seconds)
        except TimeoutError as exc:
            raise PlannerTimeoutError("AI 编排任务超过总 deadline。") from exc
        except StructuredOutputError as exc:
            raise PlannerProtocolError(f"AI 编排结果修复后仍不符合协议：{exc}") from exc
        except Exception as exc:
            raise PlannerProviderError(str(exc)) from exc
        finally:
            self.model_call_count = output.model_call_count


__all__ = [
    "ApiScenarioPlanner",
    "PlannerError",
    "PlannerProtocolError",
    "PlannerProviderError",
    "PlannerTimeoutError",
]
