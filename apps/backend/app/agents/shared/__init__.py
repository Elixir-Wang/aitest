"""Shared agent infrastructure without eager framework imports."""

from app.agents.shared.skill_runtime import ExecutableSkill, SkillDefinition, SkillReference

__all__ = ["ExecutableSkill", "SkillDefinition", "SkillReference"]
