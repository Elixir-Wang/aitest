from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.schemas.model import AiCapabilityOut, ModelAssignmentIn, ModelAssignmentOut
from app.services import model_service


router = APIRouter(prefix="/ai", tags=["ai"])
model_assignment_router = APIRouter(prefix="/model-assignments", tags=["models"])


@router.get("/capabilities", response_model=list[AiCapabilityOut])
def list_ai_capabilities(actor=Depends(current_user)) -> list[dict]:
    return model_service.list_ai_capability_rows(actor)


@model_assignment_router.get("", response_model=list[ModelAssignmentOut])
def list_model_assignments(actor=Depends(current_user)) -> list[dict]:
    return model_service.list_model_assignments(actor)


@model_assignment_router.put("/{capability_id}", response_model=ModelAssignmentOut)
def update_model_assignment(
    capability_id: str,
    payload: ModelAssignmentIn,
    actor=Depends(current_user),
) -> dict:
    return model_service.update_model_assignment(capability_id, payload, actor)
