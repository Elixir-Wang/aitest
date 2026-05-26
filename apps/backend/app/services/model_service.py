from __future__ import annotations

import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.schemas.model import ModelProviderIn
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


def _model_log_snapshot(row) -> dict:
    return {
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "api_key": row["api_key"],
        "description": row["description"],
        "status": row["status"],
    }
