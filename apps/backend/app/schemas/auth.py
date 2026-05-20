from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginOut(BaseModel):
    access_token: str
    current_user: UserOut


class CurrentUserOut(BaseModel):
    user: UserOut
    roles: list[str]
    project_permissions: dict[str, list[str]]

