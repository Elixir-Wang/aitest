import secrets

from app.agents.capabilities import get_ai_capability, list_ai_capabilities
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.schemas.model import ModelAssignmentIn, ModelProviderIn
from app.presentation.serializers import serialize_model_provider
from app.services import operation_log_service


def list_model_providers(actor) -> list[dict]:
    with connect() as db:
        rows = model_repo.list_providers(db)
        return [serialize_model_provider(row, actor["role"]) for row in rows]


def create_model_provider(payload: ModelProviderIn, actor) -> dict:
    provider_id = f"mp-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            model_repo.create_provider(
                db,
                provider_id=provider_id,
                provider=payload.provider,
                model=payload.model,
                base_url=payload.base_url,
                api_key=payload.api_key,
                description=payload.description,
                status=payload.status,
                created_by=actor["id"],
            )
        except Exception as exc:
            raise api_error(409, "MODEL_CONFLICT", "模型配置已存在。") from exc
        row = model_repo.find_provider_by_id(db, provider_id)
        result = serialize_model_provider(row, actor["role"])
    operation_log_service.record_change(
        log_type="config",
        module="model",
        action="create",
        object_type="model_provider",
        object_id=provider_id,
        object_name=f"{result['provider']} / {result['model']}",
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"新增模型配置：{result['provider']} / {result['model']}",
        after=_model_log_snapshot(result),
    )
    return result


def update_model_provider(provider_id: str, payload: ModelProviderIn, actor) -> dict:
    with connect() as db:
        existing = model_repo.find_provider_by_id(db, provider_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "模型配置不存在。")
        api_key = payload.api_key if payload.api_key else existing["api_key"]
        try:
            model_repo.update_provider(
                db,
                provider_id=provider_id,
                provider=payload.provider,
                model=payload.model,
                base_url=payload.base_url,
                api_key=api_key,
                description=payload.description,
                status=payload.status,
            )
        except Exception as exc:
            raise api_error(409, "MODEL_CONFLICT", "模型配置已存在。") from exc
        row = model_repo.find_provider_by_id(db, provider_id)
        result = serialize_model_provider(row, actor["role"])
        before = _model_log_snapshot(existing)
        after = _model_log_snapshot(row)
    operation_log_service.record_change(
        log_type="config",
        module="model",
        action="update",
        object_type="model_provider",
        object_id=provider_id,
        object_name=f"{result['provider']} / {result['model']}",
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑模型配置：{result['provider']} / {result['model']}",
        before=before,
        after=after,
    )
    return result


def delete_model_provider(provider_id: str, actor=None) -> dict:
    with connect() as db:
        existing = model_repo.find_provider_by_id(db, provider_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "模型配置不存在。")
        snapshot = _model_log_snapshot(existing)
        model_repo.delete_provider(db, provider_id)
    operation_log_service.record_change(
        log_type="config",
        module="model",
        action="delete",
        object_type="model_provider",
        object_id=provider_id,
        object_name=f"{snapshot['provider']} / {snapshot['model']}",
        actor_id=actor["id"] if actor else "system",
        actor_name=operation_log_service.actor_display_name(actor),
        source="web" if actor else "system",
        summary=f"删除模型配置：{snapshot['provider']} / {snapshot['model']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


def list_ai_capability_rows(_actor) -> list[dict]:
    return [
        {
            "id": capability.id,
            "name": capability.name,
            "description": capability.description,
            "kind": capability.kind,
        }
        for capability in list_ai_capabilities()
    ]


def list_model_assignments(_actor) -> list[dict]:
    with connect() as db:
        rows = {row["capability_id"]: row for row in model_repo.list_model_assignments(db)}
        return [_serialize_assignment(capability.id, rows.get(capability.id)) for capability in list_ai_capabilities()]


def update_model_assignment(capability_id: str, payload: ModelAssignmentIn, actor) -> dict:
    try:
        capability = get_ai_capability(capability_id)
    except KeyError as exc:
        raise api_error(404, "AI_CAPABILITY_NOT_FOUND", "AI 能力不存在。") from exc

    with connect() as db:
        existing = model_repo.find_model_assignment(db, capability_id)
        provider = model_repo.find_provider_by_id(db, payload.model_provider_id)
        if not provider:
            raise api_error(404, "MODEL_PROVIDER_NOT_FOUND", "模型配置不存在。")
        if provider["status"] != "enabled":
            raise api_error(400, "MODEL_PROVIDER_DISABLED", "不能分配已禁用的模型配置。")
        model_repo.upsert_model_assignment(
            db,
            capability_id=capability_id,
            model_provider_id=payload.model_provider_id,
        )
        row = model_repo.find_model_assignment(db, capability_id)
        result = _serialize_assignment(capability_id, row)
        before = _assignment_snapshot(existing)
        after = _assignment_snapshot(row)
    operation_log_service.record_change(
        log_type="config",
        module="model",
        action="assign_model",
        object_type="model_assignment",
        object_id=capability_id,
        object_name=capability.name,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"配置 AI 能力模型：{capability.name}",
        before=before,
        after=after,
    )
    return result


def _model_log_snapshot(row) -> dict:
    return {
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "api_key": row["api_key"],
        "description": row["description"],
        "status": row["status"],
    }


def _serialize_assignment(capability_id: str, row) -> dict:
    capability = get_ai_capability(capability_id)
    base = {
        "capability_id": capability.id,
        "capability_name": capability.name,
        "capability_description": capability.description,
        "capability_kind": capability.kind,
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
        "capability_id": row["capability_id"],
        "model_provider_id": row["model_provider_id"],
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "model_status": row["model_status"],
    }
