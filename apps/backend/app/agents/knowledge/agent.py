from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain.agents.structured_output import ToolStrategy

from app.agents.knowledge.prompts import SYSTEM_PROMPT
from app.agents.knowledge.schemas import KnowledgeQueryOutput


def knowledge_agent(model):
    return create_deep_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        backend=StateBackend(),
        response_format=ToolStrategy(KnowledgeQueryOutput),
    )
