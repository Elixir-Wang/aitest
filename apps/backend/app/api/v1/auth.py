from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import current_user, get_token
from app.schemas.auth import CurrentUserOut, LoginIn, LoginOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn) -> dict:
    return auth_service.login(payload.username, payload.password)


@router.post("/logout")
def logout(token: str = Depends(get_token)) -> dict:
    return auth_service.logout(token)


@router.get("/me", response_model=CurrentUserOut)
def me(user=Depends(current_user)) -> dict:
    return auth_service.me(user)

