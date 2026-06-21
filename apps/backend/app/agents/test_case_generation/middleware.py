"""Skill 中间件实现"""

from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import SystemMessage

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)


class SkillMiddleware(AgentMiddleware[AgentState[ResponseT], ContextT, ResponseT]):
    """动态加载 Skill 并注入到 system_prompt 的中间件

    功能：
    1. 读取主 SKILL.md
    2. 可选：读取 references/ 下的参考文档
    3. 组合内容并注入到 system_prompt
    4. 支持热更新（每次调用重新读取）

    示例：
        ```python
        skill_middleware = SkillMiddleware(
            skill_path=Path("skills/test-case-generation"),
            load_references=True
        )

        agent = create_agent(
            model=model,
            middleware=[skill_middleware],
            ...
        )
        ```
    """

    def __init__(
        self,
        skill_path: Path,
        load_references: bool = True,
        references_to_load: list[str] | None = None,
    ):
        """初始化 Skill 中间件

        Args:
            skill_path: Skill 目录路径（包含 SKILL.md 和 references/）
            load_references: 是否加载 references/ 下的文档（默认 True）
            references_to_load: 要加载的参考文档列表（None = 全部）
                示例：["examples.md", "guidelines.md"]
        """
        super().__init__()
        self.skill_path = skill_path
        self.load_references = load_references
        self.references_to_load = references_to_load

    @property
    def name(self) -> str:
        """中间件名称"""
        return "SkillMiddleware"

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """拦截模型调用，动态注入 Skill 内容

        Args:
            request: 模型请求
            handler: 原始处理器

        Returns:
            模型响应
        """
        # 1. 读取主 SKILL.md
        skill_content = self._load_skill_md()

        # 2. 读取 references（可选）
        if self.load_references:
            references_content = self._load_references()
            if references_content:
                skill_content = f"{skill_content}\n\n---\n\n# 📚 附录文档\n\n{references_content}"

        # 3. 合并到 system_prompt
        original_prompt = ""
        if request.system_message:
            original_prompt = request.system_message.content

        # 组合：基础提示词 + Skill 内容
        if original_prompt:
            enhanced_prompt = f"{original_prompt}\n\n---\n\n{skill_content}"
        else:
            enhanced_prompt = skill_content

        # 4. 创建新 request
        new_request = request.override(
            system_message=SystemMessage(content=enhanced_prompt)
        )

        # 5. 调用原始 handler
        return handler(new_request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Any],
    ) -> ModelResponse[ResponseT]:
        """异步版本的 wrap_model_call"""
        # 1. 读取主 SKILL.md
        skill_content = self._load_skill_md()

        # 2. 读取 references（可选）
        if self.load_references:
            references_content = self._load_references()
            if references_content:
                skill_content = f"{skill_content}\n\n---\n\n# 📚 附录文档\n\n{references_content}"

        # 3. 合并到 system_prompt
        original_prompt = ""
        if request.system_message:
            original_prompt = request.system_message.content

        # 组合：基础提示词 + Skill 内容
        if original_prompt:
            enhanced_prompt = f"{original_prompt}\n\n---\n\n{skill_content}"
        else:
            enhanced_prompt = skill_content

        # 4. 创建新 request
        new_request = request.override(
            system_message=SystemMessage(content=enhanced_prompt)
        )

        # 5. 异步调用原始 handler（关键修复：必须 await）
        return await handler(new_request)

    def _load_skill_md(self) -> str:
        """加载主 SKILL.md 文件

        Returns:
            Skill 内容（移除 frontmatter）

        Raises:
            FileNotFoundError: 如果 SKILL.md 不存在
        """
        skill_file = self.skill_path / "SKILL.md"

        if not skill_file.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_file}")

        content = skill_file.read_text(encoding="utf-8")

        # 移除 YAML frontmatter (--- ... ---)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()

        return content

    def _load_references(self) -> str:
        """加载 references/ 下的参考文档

        Returns:
            组合后的参考文档内容
        """
        references_dir = self.skill_path / "references"

        if not references_dir.exists():
            return ""

        # 确定要加载的文件
        if self.references_to_load:
            files_to_load = [references_dir / name for name in self.references_to_load]
        else:
            # 加载所有 .md 文件（按字母顺序）
            files_to_load = sorted(references_dir.glob("*.md"))

        # 读取并组合
        contents = []
        for file_path in files_to_load:
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                # 添加文件标识
                contents.append(f"## 📄 {file_path.stem}\n\n{content}")

        return "\n\n---\n\n".join(contents)


__all__ = ["SkillMiddleware"]
