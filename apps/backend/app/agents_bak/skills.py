from pathlib import Path
from typing import List

from app.agents.definitions import SkillDefinition
from app.agents.registry import agent_registry
from app.agents.skill_loader import load_skills


class SkillRegistry:
    def __init__(self, skills: list[SkillDefinition]) -> None:
        self._skills = {
            (skill.agent_id, skill.id): skill
            for skill in skills
        }

    def list(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get(self, skill_id: str, agent_id: str | None = None) -> SkillDefinition:
        if agent_id is not None:
            return self._skills[(agent_id, skill_id)]
        matches = [skill for (owner, current_id), skill in self._skills.items() if current_id == skill_id]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(skill_id)
        raise KeyError(f"Skill id is ambiguous without agent_id: {skill_id}")

    def select(self, skill_ids: tuple[str, ...], agent_id: str) -> List[SkillDefinition]:
        return [self.get(skill_id, agent_id=agent_id) for skill_id in skill_ids]


def discover_skill_definitions(agents_dir: Path | None = None) -> list[SkillDefinition]:
    root = agents_dir or Path(__file__).parent
    definitions: list[SkillDefinition] = []
    for agent in agent_registry.list():
        agent_path = root / agent.id
        for skill in load_skills(agent_path / "skills"):
            definitions.append(
                SkillDefinition(
                    id=skill.id,
                    name=skill.name,
                    description=skill.description,
                    instructions=skill.instructions,
                    tools=skill.tools,
                    path=skill.path,
                    enabled=skill.enabled,
                    agent_id=agent.id,
                    agent_path=str(agent_path),
                )
            )
    return definitions


skill_registry = SkillRegistry(discover_skill_definitions())
