from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..database import connect, hash_secret
from ..formatters import serialize_model_provider
from ..schemas import ModelProviderIn, ModelProviderOut
from ..security import current_user, require_admin

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers", response_model=list[ModelProviderOut])
def list_model_providers(actor=Depends(current_user)) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT * FROM model_providers ORDER BY created_at DESC, provider ASC").fetchall()
        return [serialize_model_provider(row, actor["role"]) for row in rows]


@router.post("/providers", response_model=ModelProviderOut)
def create_model_provider(payload: ModelProviderIn, actor=Depends(require_admin)) -> dict:
    provider_id = f"mp-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            db.execute(
                """
                INSERT INTO model_providers (id, provider, model, base_url, api_key_hash, api_key_mask, description, status, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    payload.provider,
                    payload.model,
                    payload.base_url,
                    hash_secret(payload.api_key) if payload.api_key else "",
                    mask_key(payload.api_key),
                    payload.description,
                    payload.status,
                    actor["id"],
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "MODEL_CONFLICT", "message": "模型配置已存在。"}) from exc
        row = db.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        return serialize_model_provider(row, actor["role"])


@router.patch("/providers/{provider_id}", response_model=ModelProviderOut)
def update_model_provider(provider_id: str, payload: ModelProviderIn, actor=Depends(require_admin)) -> dict:
    with connect() as db:
        existing = db.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "模型配置不存在。"})
        api_key_hash = existing["api_key_hash"]
        api_key_mask = existing["api_key_mask"]
        if payload.api_key:
            api_key_hash = hash_secret(payload.api_key)
            api_key_mask = mask_key(payload.api_key)
        try:
            db.execute(
                """
                UPDATE model_providers
                SET provider = ?, model = ?, base_url = ?, api_key_hash = ?, api_key_mask = ?, description = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (payload.provider, payload.model, payload.base_url, api_key_hash, api_key_mask, payload.description, payload.status, provider_id),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "MODEL_CONFLICT", "message": "模型配置已存在。"}) from exc
        row = db.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()
        return serialize_model_provider(row, actor["role"])


@router.delete("/providers/{provider_id}")
def delete_model_provider(provider_id: str, actor=Depends(require_admin)) -> dict:
    with connect() as db:
        db.execute("DELETE FROM model_providers WHERE id = ?", (provider_id,))
        return {"success": True}


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"
