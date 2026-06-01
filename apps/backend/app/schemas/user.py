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

