from pathlib import Path

from langchain.agents import create_agent

from app.agents.requirement_analysis.middleware import SkillMiddleware
from app.agents.requirement_finalization.schemas import RequirementFinalizationOutput
from app.agents.requirement_finalization.system_prompt import SYSTEM_PROMPT


def requirement_finalization_agent(model, load_references: bool = True):
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "requirement-finalization",
        load_references=load_references,
    )
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=[skill_middleware],
        response_format=RequirementFinalizationOutput,
    )


__all__ = ["requirement_finalization_agent"]
