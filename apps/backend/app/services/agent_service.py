from app.agents.capabilities import get_ai_capability, list_ai_capabilities
from app.core.exceptions import api_error
from app.schemas.agent import AgentRunIn


def list_agents(_actor) -> list[dict]:
    return [
        {
            "id": capability.id,
            "name": capability.name,
            "description": capability.description,
        }
        for capability in list_ai_capabilities()
    ]


def list_skills(_actor) -> list[dict]:
    return []


async def execute_agent(agent_id: str, payload: AgentRunIn, actor) -> dict:
    try:
        get_ai_capability(agent_id)
    except KeyError as exc:
        raise api_error(404, "AGENT_NOT_FOUND", "智能体不存在。") from exc
    _ = payload
    _ = actor
    raise api_error(501, "AGENT_RUNTIME_NOT_MIGRATED", "智能体运行时正在迁移中。")
