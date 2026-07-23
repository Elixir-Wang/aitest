from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware
from app.agents.test_point_generation.schemas import RequirementObligationExtractionResult


def requirement_obligation_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt="你是最终需求测试义务提取专家。",
        middleware=[
            SkillMiddleware(
                skill_path=Path(__file__).parent / "skills" / "test-point-obligation-extraction",
                load_references=False,
            ),
            InvalidToolCallRecoveryMiddleware(),
        ],
        response_format=ToolStrategy(RequirementObligationExtractionResult),
    )


__all__ = ["requirement_obligation_agent"]
