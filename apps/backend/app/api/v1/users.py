from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import current_user, require_admin
from app.schemas.user import UserCreateIn, UserOut, UserUpdateIn
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(actor=Depends(current_user)) -> list[dict]:
    return user_service.list_users(actor)


@router.post("", response_model=UserOut)
def create_user(payload: UserCreateIn, actor=Depends(require_admin)) -> dict:
    return user_service.create_user(payload, actor)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdateIn, actor=Depends(require_admin)) -> dict:
    return user_service.update_user(user_id, payload, actor)


@router.delete("/{user_id}")
def delete_user(user_id: str, actor=Depends(require_admin)) -> dict:
    return user_service.delete_user(user_id, actor)

