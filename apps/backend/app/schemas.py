from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

Role = str
Status = str


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    nickname: str | None = None
    role: Role
    status: Status
    project_scope: str
    description: str
    created_at: str
    updated_at: str
    last_login_at: str | None = None
    available_actions: list[str]


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


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=6)
    nickname: str | None = None
    role: Role
    status: Status = "enabled"
    project_scope: str = "全部项目"
    description: str = ""


class UserUpdateIn(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    nickname: str | None = None
    role: Role | None = None
    status: Status | None = None
    project_scope: str | None = None
    description: str | None = None


class ModelProviderOut(BaseModel):
    id: str
    provider: str
    model: str
    base_url: str
    api_key_mask: str
    description: str
    status: Status
    created_by: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ModelProviderIn(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_key: str = ""
    description: str = ""
    status: Status = "enabled"


class DashboardMetricOut(BaseModel):
    label: str
    value: str
    helper: str


class DashboardTrendPointOut(BaseModel):
    date: str
    caseAssets: int
    adoptedCases: int
    automationCases: int


class DashboardOut(BaseModel):
    scope: str
    project_id: str | None = None
    project_name: str | None = None
    metrics: list[DashboardMetricOut]
    trend: list[DashboardTrendPointOut]
