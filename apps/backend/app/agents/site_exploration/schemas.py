from typing import Literal

from pydantic import BaseModel, Field


class SiteExplorationInput(BaseModel):
    site_url: str = Field(min_length=1)
    scope: str = ""
    forbidden_paths: str = ""
    goal: str = ""
    login_strategy: str = "skip_login"
    captcha_strategy: str = "none"
    reuse_auth_state: bool = False
    has_login_credentials: bool = False


class SiteExplorationOutput(BaseModel):
    status: Literal["ready", "needs_human", "blocked"] = Field(
        description="探索启动前的智能体判断。ready 表示可以调用 Playwright runner。"
    )
    runner_contract: dict = Field(
        default_factory=dict,
        description="传递给 TS Playwright runner 的运行合同，包括 URL、范围、目标和禁止路径。",
    )
    artifact_contract: dict = Field(
        default_factory=dict,
        description="本次探索必须产出的结构化文件和 schema 版本。",
    )
    summary: str = Field(min_length=1, description="本次智能体规划结论。")
    risk_notes: list[str] = Field(default_factory=list, description="启动前发现的风险或需要人工确认的事项。")
    suggested_actions: list[str] = Field(default_factory=list, description="后续建议动作。")


class PlaywrightExplorerContract(BaseModel):
    site_url: str
    goal: str = ""
    include_paths: list[str] = []
    exclude_paths: list[str] = []


class PlaywrightExplorerResult(BaseModel):
    status: Literal["planned"]
    runner: Literal["ts_playwright"] = "ts_playwright"
    contract: PlaywrightExplorerContract
    expected_artifacts: list[str]
