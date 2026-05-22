from __future__ import annotations

from agents import Agent, Runner

from app.agents.definitions import AgentDefinition, SkillDefinition
from app.agents.registry import agent_registry
from app.agents.skills import skill_registry


def build_agent(definition: AgentDefinition, skills: list[SkillDefinition] | None = None) -> Agent:
    skill_context = _format_skill_context(skills or [])
    instructions = definition.instructions
    if skill_context:
        instructions = f"{instructions}\n\n可用技能：\n{skill_context}"
    return Agent(
        name=definition.name,
        instructions=instructions,
        model=definition.model,
    )


async def run_agent(agent_id: str, prompt: str) -> str:
    definition = agent_registry.get(agent_id)
    skills = skill_registry.select(definition.skill_ids)
    agent = build_agent(definition, skills)
    result = await Runner.run(agent, prompt)
    return result.final_output


def _format_skill_context(skills: list[SkillDefinition]) -> str:
    return "\n".join(f"- {skill.name}: {skill.description}" for skill in skills)

