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
        skill_file = self.skill_path / "SKILL.md"

        if not skill_file.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_file}")

        content = skill_file.read_text(encoding="utf-8")

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        return content

    def _load_references(self) -> str:
        references_dir = self.skill_path / "references"

        if not references_dir.exists():
            return ""

        if self.references_to_load:
            files_to_load = [references_dir / name for name in self.references_to_load]
        else:
            files_to_load = sorted(references_dir.glob("*.md"))

        contents = []
        for file_path in files_to_load:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                contents.append(f"## 📄 {file_path.stem}\n\n{content}")

        return "\n\n---\n\n".join(contents)


__all__ = ["SkillMiddleware"]
