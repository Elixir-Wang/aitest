from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.agents.document_editor.service import edit_document
from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput
from app.schemas.agent import AgentOut, AgentRunIn, AgentRunOut, SkillOut
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(actor=Depends(current_user)) -> list[dict]:
    return agent_service.list_agents(actor)


@router.get("/skills", response_model=list[SkillOut])
def list_skills(actor=Depends(current_user)) -> list[dict]:
    return agent_service.list_skills(actor)


@router.post("/document-editor/run", response_model=DocumentEditOutput)
def run_document_editor(payload: DocumentEditInput, _actor=Depends(current_user)) -> DocumentEditOutput:
    return edit_document(payload)


@router.post("/{agent_id}/run", response_model=AgentRunOut)
async def run_agent(agent_id: str, payload: AgentRunIn, actor=Depends(current_user)) -> dict:
    return await agent_service.execute_agent(agent_id, payload, actor)
