import json
from typing import Literal

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel, Field

from app.agents.rejected_case_search.schemas import RejectedCaseReference
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.test_case_generation.schemas import TestCaseGenerationResult


class GeneratedCaseConflict(BaseModel):
    generated_case_id: str
    record_id: str
    conflict_type: Literal["duplicate", "uncorrected"]
    explanation: str


class GeneratedCaseConflictResult(BaseModel):
    conflicts: list[GeneratedCaseConflict] = Field(default_factory=list)


def conflict_check_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=(
            "你是测试用例历史反例冲突检查器。只比较候选用例与提供的历史记录。"
            "block_duplicate 出现语义等价候选时返回 duplicate；generate_with_correction 的问题仍未修正时返回 uncorrected。"
            "warning_only 不产生冲突。不得扩展检查范围或编造冲突。"
        ),
        middleware=[InvalidToolCallRecoveryMiddleware()],
        response_format=ToolStrategy(GeneratedCaseConflictResult),
    )


async def check_generated_case_conflicts(
    model,
    result: TestCaseGenerationResult,
    references: list[RejectedCaseReference],
) -> GeneratedCaseConflictResult:
    payload = {
        "candidate": result.model_dump(mode="json"),
        "references": [reference.model_dump(mode="json") for reference in references],
    }
    response = await conflict_check_agent(model).ainvoke(
        {"messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
    )
    structured = response.get("structured_response") if isinstance(response, dict) else None
    if isinstance(structured, GeneratedCaseConflictResult):
        return structured
    if isinstance(structured, dict):
        return GeneratedCaseConflictResult.model_validate(structured)
    if isinstance(structured, str):
        return GeneratedCaseConflictResult.model_validate_json(structured)
    raise ValueError("测试用例历史反例冲突检查未返回结构化结果。")
