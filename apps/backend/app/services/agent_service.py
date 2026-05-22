from __future__ import annotations

from app.agents.registry import agent_registry
from app.agents.runtime import run_agent
from app.agents.skills import skill_registry
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.schemas.agent import AgentModelAssignmentIn, AgentRunIn


def list_agents(_actor) -> list[dict]:
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "model": agent.model,
            "skill_ids": list(agent.skill_ids),
        }
        for agent in agent_registry.list()
    ]


def list_skills(_actor) -> list[dict]:
    return [
        {
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "enabled": skill.enabled,
            "tool_count": len(skill.tools),
        }
        for skill in skill_registry.list()
    ]


async def execute_agent(agent_id: str, payload: AgentRunIn, _actor) -> dict:
    try:
        result = await run_agent(agent_id, payload.prompt)
    except KeyError as exc:
        raise api_error(404, "AGENT_NOT_FOUND", "智能体不存在。") from exc
    return {
        "run_id": result.run_id,
        "agent_id": result.agent_id,
        "output": result.output,
        "model": result.model,
        "model_provider_id": result.model_provider_id,
        "provider": result.provider,
        "base_url": result.base_url,
        "api_key_env": result.api_key_env,
        "skill_ids": result.skill_ids,
        "tool_names": result.tool_names,
        "raw_response_count": result.raw_response_count,
        "item_count": result.item_count,
        "usage": result.usage,
    }


def list_model_assignments(_actor) -> list[dict]:
    with connect() as db:
        rows = {row["agent_id"]: row for row in model_repo.list_agent_assignments(db)}
        assignments: list[dict] = []
        for agent in agent_registry.list():
            row = rows.get(agent.id)
            assignments.append(_serialize_assignment(agent.id, row))
        return assignments


def update_model_assignment(agent_id: str, payload: AgentModelAssignmentIn, _actor) -> dict:
    try:
        agent_registry.get(agent_id)
    except KeyError as exc:
        raise api_error(404, "AGENT_NOT_FOUND", "智能体不存在。") from exc

    with connect() as db:
        provider = model_repo.find_provider_by_id(db, payload.model_provider_id)
        if not provider:
            raise api_error(404, "MODEL_PROVIDER_NOT_FOUND", "模型配置不存在。")
        if provider["status"] != "enabled":
            raise api_error(400, "MODEL_PROVIDER_DISABLED", "不能分配已禁用的模型配置。")
        model_repo.upsert_agent_assignment(db, agent_id=agent_id, model_provider_id=payload.model_provider_id)
        row = model_repo.find_agent_assignment(db, agent_id)
        return _serialize_assignment(agent_id, row)


def _serialize_assignment(agent_id: str, row) -> dict:
    agent = agent_registry.get(agent_id)
    base = {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "agent_description": agent.description,
    }
    if not row:
        return base
    return {
        **base,
        "model_provider_id": row["model_provider_id"],
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "api_key_env": row["api_key_env"],
        "api_key_mask": row["api_key_mask"],
        "model_status": row["model_status"],
        "updated_at": row["updated_at"],
    }
