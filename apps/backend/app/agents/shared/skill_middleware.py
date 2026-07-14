"""Skill middleware shared by LangChain agents."""

from pathlib import Path
from typing import Any, Callable

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import SystemMessage

from app.agents.shared.skill_runtime import SkillDefinition


class SkillMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """Dynamically load SKILL.md and references into the system prompt."""

    def __init__(
        self,
        skill_path: Path,
        load_references: bool = True,
        references_to_load: list[str] | None = None,
    ):
        super().__init__()
        self.skill_path = skill_path
        self.load_references = load_references
        self.references_to_load = references_to_load
        self.definition = SkillDefinition.load(skill_path)

    @property
    def name(self) -> str:
        return "SkillMiddleware"

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        original_prompt = request.system_message.content if request.system_message else ""
        enhanced_prompt = self._build_enhanced_prompt(original_prompt)
        new_request = request.override(system_message=SystemMessage(content=enhanced_prompt))
        return handler(new_request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Any],
    ) -> ModelResponse[ResponseT]:
        original_prompt = request.system_message.content if request.system_message else ""
        enhanced_prompt = self._build_enhanced_prompt(original_prompt)
        new_request = request.override(system_message=SystemMessage(content=enhanced_prompt))
        return await handler(new_request)

    def _build_enhanced_prompt(self, original_prompt: str) -> str:
        skill_content = self._load_skill_md()

        if self.load_references:
            references_content = self._load_references()
            if references_content:
                skill_content = f"{skill_content}\n\n---\n\n# 📚 附录文档\n\n{references_content}"

        if original_prompt:
            return f"{original_prompt}\n\n---\n\n{skill_content}"
        return skill_content

    def _load_skill_md(self) -> str:
        return self.definition.instructions

    def _load_references(self) -> str:
        contents = []
        for reference in self.definition.select_references(self.references_to_load):
            contents.append(f"## 📄 {reference.path.stem}\n\n{reference.content}")

        return "\n\n---\n\n".join(contents)


__all__ = ["SkillMiddleware"]
