from __future__ import annotations

from app.agents.registry import agent_registry
from app.agents.runtime import run_agent
from app.agents.skills import skill_registry
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.schemas.agent import AgentModelAssignmentIn, AgentRunIn
from app.services import operation_log_service


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


async def execute_agent(agent_id: str, payload: AgentRunIn, actor) -> dict:
    try:
        result = await run_agent(agent_id, payload.prompt)
    except KeyError as exc:
        raise api_error(404, "AGENT_NOT_FOUND", "智能体不存在。") from exc
    output = {
        "run_id": result.run_id,
        "agent_id": result.agent_id,
        "output": result.output,
        "model": result.model,
        "model_provider_id": result.model_provider_id,
        "provider": result.provider,
        "base_url": result.base_url,
        "skill_ids": result.skill_ids,
        "tool_names": result.tool_names,
        "raw_response_count": result.raw_response_count,
        "item_count": result.item_count,
        "usage": result.usage,
    }
    operation_log_service.record_agent_run(
        module="agent",
        action="run",
        object_type="agent",
        object_id=result.agent_id,
        object_name=result.agent_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="agent",
        result="success",
        summary=f"执行智能体：{result.agent_id}",
        after={
            "run_id": result.run_id,
            "model": result.model,
            "model_provider_id": result.model_provider_id,
            "skill_ids": result.skill_ids,
            "tool_names": result.tool_names,
            "raw_response_count": result.raw_response_count,
            "item_count": result.item_count,
            "usage": result.usage,
        },
        task_id=result.run_id,
    )
    return output


def list_model_assignments(_actor) -> list[dict]:
    with connect() as db:
        rows = {row["agent_id"]: row for row in model_repo.list_agent_assignments(db)}
        assignments: list[dict] = []
        for agent in agent_registry.list():
            row = rows.get(agent.id)
            assignments.append(_serialize_assignment(agent.id, row))
        return assignments


def update_model_assignment(agent_id: str, payload: AgentModelAssignmentIn, actor) -> dict:
    try:
        agent_registry.get(agent_id)
    except KeyError as exc:
        raise api_error(404, "AGENT_NOT_FOUND", "智能体不存在。") from exc

    with connect() as db:
        existing = model_repo.find_agent_assignment(db, agent_id)
        provider = model_repo.find_provider_by_id(db, payload.model_provider_id)
        if not provider:
            raise api_error(404, "MODEL_PROVIDER_NOT_FOUND", "模型配置不存在。")
        if provider["status"] != "enabled":
            raise api_error(400, "MODEL_PROVIDER_DISABLED", "不能分配已禁用的模型配置。")
        model_repo.upsert_agent_assignment(db, agent_id=agent_id, model_provider_id=payload.model_provider_id)
        row = model_repo.find_agent_assignment(db, agent_id)
        result = _serialize_assignment(agent_id, row)
        before = _assignment_snapshot(existing)
        after = _assignment_snapshot(row)
    operation_log_service.record_change(
        log_type="config",
        module="agent",
        action="assign_model",
        object_type="agent_model_assignment",
        object_id=agent_id,
        object_name=result["agent_name"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"配置智能体模型：{result['agent_name']}",
        before=before,
        after=after,
    )
    return result


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
        "api_key": row["api_key"],
        "model_status": row["model_status"],
        "updated_at": row["updated_at"],
    }


def _assignment_snapshot(row) -> dict:
    if not row:
        return {}
    return {
        "agent_id": row["agent_id"],
        "model_provider_id": row["model_provider_id"],
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "model_status": row["model_status"],
    }
