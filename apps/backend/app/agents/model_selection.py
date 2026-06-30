from dataclasses import dataclass
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from app.agents.capabilities import get_ai_capability
from app.core.db import connect
from app.repositories import model_repo


@dataclass(frozen=True)
class ModelSelection:
    provider: str
    model: str
    base_url: str | None
    api_key: str


def resolve_model_selection(capability_id: str) -> ModelSelection:
    capability = get_ai_capability(capability_id)
    with connect() as db:
        assignment = model_repo.find_model_assignment(db, capability_id)
    if not assignment:
        raise ValueError(f"AI 能力未分配可用模型配置，无法运行：{capability.name}")
    if assignment["model_status"] != "enabled":
        raise ValueError(f"AI 能力分配的模型配置未启用，无法运行：{capability.name}")
    if not assignment["api_key"]:
        raise ValueError(f"模型配置未保存 API Key，无法用于 AI 能力运行：{capability.name}")
    return ModelSelection(
        provider=assignment["provider"],
        model=assignment["model"],
        base_url=assignment["base_url"] or None,
        api_key=assignment["api_key"],
    )


def build_agent_model(selection: ModelSelection, *, extra_body: dict | None = None):
    kwargs = {}
    if extra_body is not None:
        kwargs["extra_body"] = extra_body
    kwargs["use_responses_api"] = should_use_responses_api(selection)
    return ChatOpenAI(
        model=selection.model,
        api_key=SecretStr(selection.api_key),
        base_url=selection.base_url,
        temperature=0,
        **kwargs,
    )


def should_use_responses_api(selection: ModelSelection) -> bool | None:
    if _is_official_openai_endpoint(selection):
        return None
    return False


def _is_official_openai_endpoint(selection: ModelSelection) -> bool:
    if selection.provider.strip().lower() != "openai":
        return False
    base_url = (selection.base_url or "").rstrip("/")
    return base_url in {"", "https://api.openai.com/v1", "https://api.openai.com"}
