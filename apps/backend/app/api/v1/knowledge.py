from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.services.knowledge import service as knowledge_service

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["knowledge"])


@router.get("/builds")
def list_knowledge_builds(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return knowledge_service.list_builds(project_id, actor)


@router.post("/builds")
async def generate_knowledge_build(project_id: str, actor=Depends(current_user)) -> dict:
    return await knowledge_service.generate_build(project_id, actor)


@router.get("/builds/{build_id}")
def get_knowledge_build(project_id: str, build_id: str, actor=Depends(current_user)) -> dict:
    return knowledge_service.get_build(project_id, build_id, actor)


@router.post("/builds/{build_id}/publish")
def publish_knowledge_build(project_id: str, build_id: str, actor=Depends(current_user)) -> dict:
    return knowledge_service.publish_build(project_id, build_id, actor)


@router.get("/builds/{build_id}/pages/{page_id}")
def get_knowledge_page(project_id: str, build_id: str, page_id: str, actor=Depends(current_user)) -> dict:
    return knowledge_service.get_page(project_id, build_id, page_id, actor)
