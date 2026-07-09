from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.api_automation import ApiAutomationGenerationResult
from app.agents.shared.skill_middleware import SkillMiddleware


def api_automation_generation_agent(
    model,
    load_references: bool = True,
    base_prompt: str | None = None,
):
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "api-automation-case-generation",
        load_references=load_references,
    )

    if base_prompt is None:
        base_prompt = "你是接口自动化测试用例生成专家。"

    return create_agent(
        model=model,
        tools=[],
        system_prompt=base_prompt,
        middleware=[skill_middleware],
        response_format=ApiAutomationGenerationResult,
    )


__all__ = ["api_automation_generation_agent"]
