from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.agents.test_point_generation.agent import test_point_generation_agent
import json

from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    RequirementObligation,
    TestPointGenerationInput,
    TestPointGenerationResult,
)


CAPABILITY_ID = "test_point_generation"


async def generate_test_points(
    input_data: TestPointGenerationInput,
    *,
    obligations: list[RequirementObligation],
    existing_points: list[GeneratedTestPoint] | None = None,
    missing_obligation_keys: list[str] | None = None,
) -> TestPointGenerationResult:
    if not input_data.requirement_content.strip():
        raise ValueError("最终需求内容为空，无法生成测试点。")
    content = "\n".join(
        [
            f"需求名称: {input_data.requirement_name}",
            f"最终需求版本 ID: {input_data.requirement_version_id}",
            "",
            "最终需求文档:",
            input_data.requirement_content,
            "",
            "必须覆盖的最终需求义务:",
            json.dumps([item.model_dump() for item in obligations], ensure_ascii=False, indent=2),
            "",
            "已生成测试点:",
            json.dumps([item.model_dump() for item in existing_points or []], ensure_ascii=False, indent=2),
            "",
            "本轮仅需补齐的义务 ID:",
            json.dumps(missing_obligation_keys or [], ensure_ascii=False),
            "",
            "请使用 test-point-generation skill 生成结构化测试点。",
        ]
    )
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    result = await test_point_generation_agent(model).ainvoke({"messages": [{"role": "user", "content": content}]})
    if not isinstance(result, dict) or not result.get("structured_response"):
        raise ValueError("测试点生成智能体未返回结构化结果。")
    structured = result["structured_response"]
    return structured if isinstance(structured, TestPointGenerationResult) else TestPointGenerationResult.model_validate(structured)


__all__ = ["generate_test_points"]
