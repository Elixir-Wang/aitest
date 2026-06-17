from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas import RequirementAnalysisAgentOutput
from app.agents.requirement_analysis.system_prompt import REQUIREMENT_ANALYSIS_SYSTEM_PROMPT
from app.core.settings import BACKEND_ROOT


def requirement_analysis_agent(model):
    from deepagents import create_deep_agent
    from deepagents.backends.filesystem import FilesystemBackend
    from deepagents.middleware.skills import SkillsMiddleware

    backend = FilesystemBackend(root_dir=BACKEND_ROOT)
    return create_deep_agent(
        model=model,
        tools=[],
        backend=backend,
        middleware=[
            SkillsMiddleware(
                backend=backend,
                sources=[
                    ("/app/agents/requirement_analysis/skills", "RequirementAnalysis"),
                ],
            )
        ],
        system_prompt=REQUIREMENT_ANALYSIS_SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementAnalysisAgentOutput),
    )


__all__ = ["requirement_analysis_agent"]
