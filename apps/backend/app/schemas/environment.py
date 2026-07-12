from pydantic import BaseModel, Field


class ExplorationEnvironmentOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    name: str
    site_url: str
    username: str
    login_strategy: str
    captcha_strategy: str = "none"
    reuse_auth_state: bool = True
    has_saved_credentials: bool = False
    auth_state_status: str = "none"
    auth_state_expires_at: str | None = None
    auth_state_message: str = ""
    description: str
    updated_at: str


class ExplorationEnvironmentCreateIn(BaseModel):
    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    site_url: str = Field(min_length=1)
    username: str = ""
    password: str = ""
    login_strategy: str = "skip_login"
    captcha_strategy: str = "none"
    reuse_auth_state: bool = True
    description: str = ""


class ExplorationEnvironmentUpdateIn(BaseModel):
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
    has_saved_credentials: bool = False
    message: str


class AutoAuthStatusOut(BaseModel):
    status: str
    message: str
    updated_at: str | None = None
    last_error_code: str = ""
