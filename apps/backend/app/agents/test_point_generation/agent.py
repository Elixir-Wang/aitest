from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware
from app.agents.test_point_generation.schemas import TestPointGenerationDraftResult


def test_point_generation_agent(model, load_references: bool = True, base_prompt: str | None = None):
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "test-point-generation",
        load_references=load_references,
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=base_prompt or "你是业务测试点设计专家。",
        middleware=[skill_middleware, InvalidToolCallRecoveryMiddleware()],
        response_format=ToolStrategy(TestPointGenerationDraftResult),
    )


__all__ = ["test_point_generation_agent"]
