import json
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel, ConfigDict, Field

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.schemas.performance_test import PerformanceSseMatch, PerformanceSseMetric


CAPABILITY_ID = "performance_script_generation"


class SseMetricSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[PerformanceSseMetric] = Field(min_length=2, max_length=20)
    end_rule: PerformanceSseMatch | None = None


def suggest_sse_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection).with_structured_output(SseMetricSuggestion)
    agent = create_agent(
        model=model,
        tools=[],
        system_prompt=(
            "你是 SSE 性能指标规则识别器。只能根据输入的真实事件样本输出声明式匹配规则。"
            "必须生成 call_llm_start 和 first_answer 两个首次指标；优先识别 event_type 字段；"
            "结束规则优先使用 query_end。不得输出 Python、脚本、网络请求或样本包装层路径。"
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
