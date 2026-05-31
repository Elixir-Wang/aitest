from __future__ import annotations

from dataclasses import dataclass

from agents.models.openai_provider import OpenAIProvider

from app.core.db import connect
from app.repositories import model_repo


@dataclass(frozen=True)
class AgentModelSelection:
    model: str
    model_provider_id: str
    provider: str
    base_url: str
    api_key: str
    model_status: str


def resolve_agent_model_selection(agent_id: str) -> AgentModelSelection:
    with connect() as db:
        assignment = model_repo.find_agent_assignment(db, agent_id)
    if not assignment:
        raise ValueError("智能体未分配可用模型配置，无法运行。")
    if assignment["model_status"] != "enabled":
        raise ValueError("智能体分配的模型配置未启用，无法运行。")
    if not assignment["api_key"]:
        raise ValueError("模型配置未保存 API Key，无法用于智能体运行。")
    return AgentModelSelection(
        model=assignment["model"],
        model_provider_id=assignment["model_provider_id"],
        provider=assignment["provider"],
        base_url=assignment["base_url"],
        api_key=assignment["api_key"],
        model_status=assignment["model_status"],
    )


def build_model_provider(selection: AgentModelSelection) -> OpenAIProvider:
    provider = normalize_provider(selection.provider)
    if provider not in {"openai", "openai-compatible"}:
        raise ValueError(f"暂不支持的模型供应商：{selection.provider}")
    return OpenAIProvider(
        api_key=selection.api_key,
        base_url=selection.base_url or None,
        use_responses=provider == "openai",
    )


def normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    aliases = {
        "deepseek": "openai-compatible",
        "openai compatible": "openai-compatible",
        "openai_compatible": "openai-compatible",
    }
    return aliases.get(normalized, normalized)
