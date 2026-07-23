from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.shared.skill_middleware import SkillMiddleware
from app.agents.manual_test_case_generation.schemas import ManualTestCaseGenerationResult


def manual_test_case_generation_agent(model):
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "manual-test-case-generation",
        load_references=True,
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt="你是手工测试用例生成专家。",
        middleware=[skill_middleware],
        response_format=ToolStrategy(ManualTestCaseGenerationResult),
    )


__all__ = ["manual_test_case_generation_agent"]
