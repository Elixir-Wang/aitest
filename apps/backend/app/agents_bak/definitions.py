from dataclasses import dataclass, field
from typing import Any

from agents import FunctionTool


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    instructions: str = ""
    tools: tuple[FunctionTool, ...] = field(default_factory=tuple)
    path: str = ""
    enabled: bool = True
    agent_id: str | None = None
    agent_path: str = ""


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    instructions: str
    model: str = "gpt-5.4-mini"
    skill_ids: tuple[str, ...] = field(default_factory=tuple)
    sort_order: int = 100
    output_type: type[Any] | None = None
