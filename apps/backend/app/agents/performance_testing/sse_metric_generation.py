import json
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel, ConfigDict, Field

from app.agents.model_selection import build_agent_model, resolve_model_selection
CAPABILITY_ID = "performance_script_generation"


class SseMetricCandidateSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    category: Literal[
        "first_output",
        "milestone_start",
        "milestone_end",
        "completion",
        "first_external_action",
        "state_transition",
        "custom_event",
    ] = "custom_event"
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)
    uncertainty: str | None = Field(default=None, max_length=500)


class SseMetricSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[SseMetricCandidateSuggestion] = Field(default_factory=list, max_length=8)
    end_rule_candidate_fact_id: str | None = Field(default=None, max_length=64)
    summary: str = Field(default="", max_length=500)


def suggest_sse_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection).with_structured_output(SseMetricSuggestion)
    agent = create_agent(
        model=model,
        tools=[],
        system_prompt=(
            "你是通用 SSE 性能指标发现分析器。只能分析输入中的真实事件事实。"
            "不得假设接口属于聊天、LLM 或工作流，不得预设任何固定事件或指标。"
            "候选只能引用输入中存在的 fact_id；不得自行创建事件名、JSONPath、字段值或正式指标 ID。"
            "优先推荐首次有效输出、关键阶段开始、关键阶段完成、整体完成和重要外部动作。"
            "降低心跳、日志、调试、确认和随机字段的优先级。证据不足时降低置信度并说明不确定性。"
            "可以返回零至八个候选，不得为满足数量生成低质量指标。不得输出代码或网络请求。"
        ),
        response_format=ToolStrategy(SseMetricSuggestion),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"INPUT={json.dumps(payload, ensure_ascii=False, sort_keys=True)}"}]}
    )
    generated = result.get("structured_response") if isinstance(result, dict) else None
    suggestion = generated if isinstance(generated, SseMetricSuggestion) else SseMetricSuggestion.model_validate(generated)
    return suggestion.model_dump(mode="json")


__all__ = ["suggest_sse_metrics"]
