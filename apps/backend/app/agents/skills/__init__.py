from __future__ import annotations

from app.agents.definitions import SkillDefinition
from app.agents.skills.requirement_document_reader import requirement_document_reader_skill
from app.agents.skills.requirement_file_to_markdown import requirement_file_to_markdown_skill
from app.agents.skills.test_case_designer import test_case_designer_skill


class SkillRegistry:
    def __init__(self, skills: list[SkillDefinition]) -> None:
        self._skills = {skill.id: skill for skill in skills}

    def list(self) -> list[SkillDefinition]:
        return list(self._skills.values())

    def get(self, skill_id: str) -> SkillDefinition:
        return self._skills[skill_id]

    def select(self, skill_ids: tuple[str, ...]) -> list[SkillDefinition]:
        return [self._skills[skill_id] for skill_id in skill_ids if skill_id in self._skills and self._skills[skill_id].enabled]


skill_registry = SkillRegistry(
    [
        requirement_file_to_markdown_skill,
        requirement_document_reader_skill,
        test_case_designer_skill,
    ]
)
