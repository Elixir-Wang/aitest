import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies.auth import current_user
from app.schemas.knowledge import KnowledgeQueryRequest
from app.services.knowledge import service as knowledge_service

router = APIRouter(prefix="/projects/{project_id}/knowledge", tags=["knowledge"])
global_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/query")
async def query_project_knowledge(
    project_id: str,
    payload: KnowledgeQueryRequest,
    actor=Depends(current_user),
) -> dict:
    return await knowledge_service.query_project_knowledge(project_id, actor, payload)


@router.post("/query/stream")
def stream_project_knowledge_query(
    project_id: str,
    payload: KnowledgeQueryRequest,
    actor=Depends(current_user),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in knowledge_service.stream_project_knowledge_query(project_id, actor, payload):
                event_type = str(event.get("type") or "message")
                data = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=_json_default)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as exc:
            data = json.dumps(
                {
                    "type": "error",
                    "message": str(exc) or "项目知识库流式查询失败。",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@global_router.get("/conversations")
def list_all_project_knowledge_conversations(actor=Depends(current_user)) -> list[dict]:
    return knowledge_service.list_all_project_knowledge_conversations(actor)


@global_router.get("/conversations/{conversation_id}")
def get_all_project_knowledge_conversation(
    conversation_id: str,
    actor=Depends(current_user),
) -> dict:
    return knowledge_service.get_all_project_knowledge_conversation(conversation_id, actor)


@global_router.delete("/conversations/{conversation_id}")
def delete_all_project_knowledge_conversation(
    conversation_id: str,
    actor=Depends(current_user),
) -> dict:
    return knowledge_service.delete_all_project_knowledge_conversation(conversation_id, actor)


@global_router.post("/query/stream")
def stream_all_project_knowledge_query(
    payload: KnowledgeQueryRequest,
    actor=Depends(current_user),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in knowledge_service.stream_all_project_knowledge_query(actor, payload):
                event_type = str(event.get("type") or "message")
                data = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=_json_default)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as exc:
            data = json.dumps(
                {
                    "type": "error",
                    "message": str(exc) or "项目知识库流式查询失败。",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
