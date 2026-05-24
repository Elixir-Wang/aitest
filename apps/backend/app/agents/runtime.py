from __future__ import annotations

from dataclasses import dataclass, field
import secrets
from typing import Any

from agents import Agent, RunConfig, Runner, set_tracing_disabled
from agents.models.openai_provider import OpenAIProvider

from app.agents.definitions import AgentDefinition, SkillDefinition
from app.agents.registry import agent_registry
from app.agents.skills import skill_registry
from app.core.db import connect
from app.core.logging import agent_logger
from app.repositories import model_repo


set_tracing_disabled(True)


@dataclass(frozen=True)
class AgentModelSelection:
    model: str
    model_provider_id: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_status: str | None = None
    using_assignment: bool = False


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    agent_id: str
    output: Any
    model: str
    model_provider_id: str | None = None
    provider: str | None = None
    base_url: str | None = None
    skill_ids: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    raw_response_count: int = 0
    item_count: int = 0
    usage: dict[str, Any] | None = None


def build_agent(definition: AgentDefinition, skills: list[SkillDefinition] | None = None) -> Agent:
    selected_skills = skills or []
    skill_instructions = _format_skill_instructions(selected_skills)
    instructions = definition.instructions
    if skill_instructions:
        instructions = f"{instructions}\n\n{skill_instructions}"
    tools = [tool for skill in selected_skills for tool in skill.tools]
    model_selection = resolve_agent_model_selection(definition)
    return Agent(
        name=definition.name,
        instructions=instructions,
        model=model_selection.model,
        tools=tools,
        output_type=definition.output_type,
    )


async def run_agent(agent_id: str, prompt: str) -> AgentRunResult:
    definition = agent_registry.get(agent_id)
    skills = skill_registry.select(definition.skill_ids, agent_id=definition.id)
    model_selection = resolve_agent_model_selection(definition)
    skill_names = [s.name for s in skills]
    skill_ids = [s.id for s in skills]
    tool_names = _tool_names(skills)
    run_id = f"agrun-{secrets.token_hex(8)}"

    agent_logger.info(
        "Agent run started | run={run_id} agent={agent_id} model={model} provider={provider} skills={skills} prompt_len={prompt_len}",
        run_id=run_id,
        agent_id=agent_id,
        model=model_selection.model,
        provider=model_selection.provider or "default",
        skills=skill_names,
        prompt_len=len(prompt),
    )

    try:
        agent = build_agent(definition, skills)
        result = await Runner.run(
            agent,
            prompt,
            run_config=RunConfig(
                model=model_selection.model,
                model_provider=_build_model_provider(model_selection),
                workflow_name="ai-testing-agent-run",
                trace_id=run_id,
                group_id=agent_id,
                trace_metadata={
                    "agent_id": agent_id,
                    "agent_name": definition.name,
                    "skill_ids": ",".join(skill_ids),
                    "model": model_selection.model,
                    "model_provider_id": model_selection.model_provider_id or "",
                    "provider": model_selection.provider or "",
                    "base_url": model_selection.base_url or "",
                },
            ),
        )
        output = _serialize_final_output(result.final_output)
        run_result = AgentRunResult(
            run_id=run_id,
            agent_id=agent_id,
            output=output,
            model=model_selection.model,
            model_provider_id=model_selection.model_provider_id,
            provider=model_selection.provider,
            base_url=model_selection.base_url,
            skill_ids=skill_ids,
            tool_names=tool_names,
            raw_response_count=len(getattr(result, "raw_responses", []) or []),
            item_count=len(getattr(result, "new_items", []) or []),
            usage=_extract_usage(result),
        )
        agent_logger.info(
            "Agent run completed | run={run_id} agent={agent_id} output_len={output_len} raw_responses={raw_response_count} items={item_count}",
            run_id=run_id,
            agent_id=agent_id,
            output_len=len(str(output)),
            raw_response_count=run_result.raw_response_count,
            item_count=run_result.item_count,
        )
        return run_result
    except Exception as exc:
        agent_logger.error(
            "Agent run failed | run={run_id} agent={agent_id} error={error}",
            run_id=run_id,
            agent_id=agent_id,
            error=str(exc),
        )
        raise


def resolve_agent_model(definition: AgentDefinition) -> str:
    return resolve_agent_model_selection(definition).model


def resolve_agent_model_selection(definition: AgentDefinition) -> AgentModelSelection:
    with connect() as db:
        assignment = model_repo.find_agent_assignment(db, definition.id)
    if assignment and assignment["model_status"] == "enabled":
        return AgentModelSelection(
            model=assignment["model"],
            model_provider_id=assignment["model_provider_id"],
            provider=assignment["provider"],
            base_url=assignment["base_url"],
            api_key=assignment["api_key"],
            model_status=assignment["model_status"],
            using_assignment=True,
        )
    return AgentModelSelection(model=definition.model)


def _format_skill_instructions(skills: list[SkillDefinition]) -> str:
    blocks: list[str] = []
    for skill in skills:
        if skill.instructions:
            blocks.append(f"## Skill: {skill.name}\n{skill.instructions}")
        else:
            blocks.append(f"## Skill: {skill.name}\n{skill.description}")
    return "\n\n".join(blocks)


def _tool_names(skills: list[SkillDefinition]) -> list[str]:
    names: list[str] = []
    for skill in skills:
        for tool in skill.tools:
            name = getattr(tool, "name", "") or getattr(tool, "__name__", "") or tool.__class__.__name__
            names.append(str(name))
    return names


def _build_model_provider(selection: AgentModelSelection):
    if not selection.using_assignment:
        raise ValueError("智能体未分配可用模型配置，无法运行。")
    provider = _normalize_provider(selection.provider)
    if provider not in {"openai", "openai-compatible"}:
        raise ValueError(f"暂不支持的模型供应商：{selection.provider}")

    api_key = _resolve_api_key(selection)
    return OpenAIProvider(
        api_key=api_key,
        base_url=selection.base_url or None,
        use_responses=provider == "openai",
    )


def _normalize_provider(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    aliases = {
        "deepseek": "openai-compatible",
        "openai compatible": "openai-compatible",
        "openai_compatible": "openai-compatible",
    }
    return aliases.get(normalized, normalized)


def _resolve_api_key(selection: AgentModelSelection) -> str:
    if selection.api_key:
        return selection.api_key
    raise ValueError("模型配置未保存 API Key，无法用于智能体运行。")


def _extract_usage(result: object) -> dict[str, Any] | None:
    usage = getattr(result, "usage", None)
    if usage is None:
        raw_responses = getattr(result, "raw_responses", []) or []
        for response in reversed(raw_responses):
            usage = getattr(response, "usage", None)
            if usage is not None:
                break
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        return usage.model_dump()
    if isinstance(usage, dict):
        return usage
    keys = (
        *vars(usage).keys(),
        "requests",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    )
    data: dict[str, Any] = {}
    for key in dict.fromkeys(keys):
        if not hasattr(usage, key):
            continue
        value = getattr(usage, key)
        if isinstance(value, (str, int, float, bool, type(None))):
            data[key] = value
    return data


def _serialize_final_output(output: object) -> Any:
    if hasattr(output, "model_dump"):
        return output.model_dump()
    return output
