from __future__ import annotations

import secrets

from fastapi import HTTPException

from app.core.db import connect
from app.core.security import hash_secret
from app.repositories import model_repo
from app.schemas.model import ModelProviderIn
from app.services.serializers import serialize_model_provider


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
                api_key_hash=hash_secret(payload.api_key) if payload.api_key else "",
                api_key_mask=mask_key(payload.api_key),
                description=payload.description,
                status=payload.status,
                created_by=actor["id"],
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "MODEL_CONFLICT", "message": "模型配置已存在。"}) from exc
        row = model_repo.find_provider_by_id(db, provider_id)
        return serialize_model_provider(row, actor["role"])


def update_model_provider(provider_id: str, payload: ModelProviderIn, actor) -> dict:
    with connect() as db:
        existing = model_repo.find_provider_by_id(db, provider_id)
        if not existing:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "模型配置不存在。"})
        api_key_hash = existing["api_key_hash"]
        api_key_mask = existing["api_key_mask"]
        if payload.api_key:
            api_key_hash = hash_secret(payload.api_key)
            api_key_mask = mask_key(payload.api_key)
        try:
            model_repo.update_provider(
                db,
                provider_id=provider_id,
                provider=payload.provider,
                model=payload.model,
                base_url=payload.base_url,
                api_key_hash=api_key_hash,
                api_key_mask=api_key_mask,
                description=payload.description,
                status=payload.status,
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "MODEL_CONFLICT", "message": "模型配置已存在。"}) from exc
        row = model_repo.find_provider_by_id(db, provider_id)
        return serialize_model_provider(row, actor["role"])


def delete_model_provider(provider_id: str) -> dict:
    with connect() as db:
        model_repo.delete_provider(db, provider_id)
        return {"success": True}


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"

