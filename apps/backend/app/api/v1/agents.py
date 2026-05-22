from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.schemas.agent import AgentModelAssignmentIn, AgentModelAssignmentOut, AgentOut, AgentRunIn, AgentRunOut, SkillOut
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(actor=Depends(current_user)) -> list[dict]:
    return agent_service.list_agents(actor)


@router.get("/skills", response_model=list[SkillOut])
def list_skills(actor=Depends(current_user)) -> list[dict]:
    return agent_service.list_skills(actor)


@router.get("/model-assignments", response_model=list[AgentModelAssignmentOut])
def list_model_assignments(actor=Depends(current_user)) -> list[dict]:
    return agent_service.list_model_assignments(actor)


@router.put("/{agent_id}/model-assignment", response_model=AgentModelAssignmentOut)
def update_model_assignment(agent_id: str, payload: AgentModelAssignmentIn, actor=Depends(current_user)) -> dict:
    return agent_service.update_model_assignment(agent_id, payload, actor)


@router.post("/{agent_id}/run", response_model=AgentRunOut)
async def run_agent(agent_id: str, payload: AgentRunIn, actor=Depends(current_user)) -> dict:
    return await agent_service.execute_agent(agent_id, payload, actor)
