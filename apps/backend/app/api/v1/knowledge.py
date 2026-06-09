from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.schemas.knowledge import KnowledgeQueryRequest
from app.services.knowledge import service as knowledge_service

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["knowledge"])


@router.post("/query")
async def query_project_knowledge(
    project_id: str,
    payload: KnowledgeQueryRequest,
    actor=Depends(current_user),
) -> dict:
    return await knowledge_service.query_project_knowledge(project_id, actor, payload)


@router.get("/conversations")
def list_project_knowledge_conversations(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return knowledge_service.list_project_knowledge_conversations(project_id, actor)


@router.get("/conversations/{conversation_id}")
def get_project_knowledge_conversation(
    project_id: str,
    conversation_id: str,
    actor=Depends(current_user),
) -> dict:
    return knowledge_service.get_project_knowledge_conversation(project_id, conversation_id, actor)


@router.delete("/conversations/{conversation_id}")
def delete_project_knowledge_conversation(
    project_id: str,
    conversation_id: str,
    actor=Depends(current_user),
) -> dict:
    return knowledge_service.delete_project_knowledge_conversation(project_id, conversation_id, actor)
