from pydantic import BaseModel, Field


class ProjectEnvironmentOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    name: str
    site_url: str
    username: str
    password_mask: str
    login_strategy: str
    captcha_strategy: str = "none"
    reuse_auth_state: bool = True
    auth_state_status: str = "none"
    auth_state_expires_at: str | None = None
    description: str
    created_at: str
    updated_at: str
    available_actions: list[str]


class ProjectEnvironmentCreateIn(BaseModel):
    project_id: str | None = None
    name: str = Field(min_length=1)
    site_url: str = Field(min_length=1)
    username: str = ""
    password: str = ""
    login_strategy: str = "skip_login"
    captcha_strategy: str = "none"
    reuse_auth_state: bool = True
    description: str = ""


class ProjectEnvironmentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    site_url: str | None = Field(default=None, min_length=1)
    username: str | None = None
    password: str | None = None
    login_strategy: str | None = None
    captcha_strategy: str | None = None
    reuse_auth_state: bool | None = None
    description: str | None = None


class ManualAuthSessionOut(BaseModel):
    session_id: str
    status: str
    auth_state_status: str = "none"
    auth_state_expires_at: str | None = None
    message: str
