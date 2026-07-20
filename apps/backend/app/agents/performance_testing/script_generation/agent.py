"""Agent definition for controlled Locust script plan generation."""

from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware
from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan


def performance_script_generation_agent(
    model,
    load_references: bool = True,
    base_prompt: str | None = None,
):
    """Create the structured-output Agent used to generate a Locust plan."""
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "performance-script-generation",
        load_references=load_references,
    )
    if base_prompt is None:
        base_prompt = (
            "你是性能测试脚本计划生成专家。只能基于输入白名单生成 LocustScriptPlan，"
            "不得新增接口、导入、文件或进程能力。"
        )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=base_prompt,
        middleware=[skill_middleware, InvalidToolCallRecoveryMiddleware()],
        response_format=ToolStrategy(LocustScriptPlan),
    )


__all__ = ["performance_script_generation_agent"]
