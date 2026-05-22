from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    enabled: bool = True


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    instructions: str
    model: str = "gpt-5.4-mini"
    skill_ids: tuple[str, ...] = field(default_factory=tuple)

