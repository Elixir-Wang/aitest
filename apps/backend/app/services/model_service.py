from __future__ import annotations

import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.schemas.model import ModelProviderIn
from app.presentation.serializers import serialize_model_provider


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
        return serialize_model_provider(row, actor["role"])


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
        return serialize_model_provider(row, actor["role"])


def delete_model_provider(provider_id: str) -> dict:
    with connect() as db:
        model_repo.delete_provider(db, provider_id)
        return {"success": True}
