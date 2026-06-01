from dataclasses import dataclass

from app.agents.capabilities import CapabilityKind, get_ai_capability
from app.core.db import connect
from app.repositories import model_repo


@dataclass(frozen=True)
class ModelSelection:
    capability_id: str
    capability_kind: CapabilityKind
    model_provider_id: str
    provider: str
    model: str
    base_url: str | None
    api_key: str
    model_status: str


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
        capability_id=capability.id,
        capability_kind=capability.kind,
        model_provider_id=assignment["model_provider_id"],
        provider=assignment["provider"],
        model=assignment["model"],
        base_url=assignment["base_url"] or None,
        api_key=assignment["api_key"],
        model_status=assignment["model_status"],
    )


def normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    aliases = {
        "deepseek": "openai-compatible",
        "openai compatible": "openai-compatible",
        "openai_compatible": "openai-compatible",
    }
    return aliases.get(normalized, normalized)
