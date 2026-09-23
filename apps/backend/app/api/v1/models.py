from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.model import BuiltinModelLoadIn, BuiltinModelLoadOut, ModelProviderIn, ModelProviderOut
from app.services import builtin_model_service, model_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers", response_model=list[ModelProviderOut])
def list_model_providers(actor=Depends(current_user)) -> list[dict]:
    return model_service.list_model_providers(actor)


@router.post("/providers", response_model=ModelProviderOut)
def create_model_provider(payload: ModelProviderIn, actor=Depends(require_admin)) -> dict:
    return model_service.create_model_provider(payload, actor)


@router.post("/providers/load-builtin", response_model=BuiltinModelLoadOut)
def load_builtin_model_providers(payload: BuiltinModelLoadIn, actor=Depends(current_user)) -> dict:
    return builtin_model_service.load_builtin_models(payload.password, actor)


@router.patch("/providers/{provider_id}", response_model=ModelProviderOut)
def update_model_provider(provider_id: str, payload: ModelProviderIn, actor=Depends(require_admin)) -> dict:
    return model_service.update_model_provider(provider_id, payload, actor)


@router.delete("/providers/{provider_id}")
def delete_model_provider(provider_id: str, actor=Depends(require_admin)) -> dict:
    return model_service.delete_model_provider(provider_id, actor)


@router.post("/providers/{provider_id}/test")
def test_model_provider(provider_id: str, actor=Depends(current_user)) -> dict:
    return model_service.test_model_provider(provider_id, actor)
