"""
Page Exploration Skills Loader

加载和管理页面探索 Agent 的领域知识（Skills）
"""

from pathlib import Path
from typing import List


class Skill:
    """Skill 数据模型"""

    def __init__(self, name: str, content: str, path: Path):
        self.name = name           # skill 名称，如 "locator_best_practices"
        self.content = content     # SKILL.md 的完整内容
        self.path = path           # 文件路径

    def __repr__(self):
        return f"Skill(name={self.name}, path={self.path})"


class SkillsLoader:
    """Skills 加载器 - 从文件系统加载 Skill 定义"""

    def __init__(self, skills_dir: Path = None):
        if skills_dir is None:
            # 默认指向当前模块的 skills 目录
            skills_dir = Path(__file__).parent
        self.skills_dir = skills_dir

    def load_skill(self, skill_name: str) -> Skill:
        """
        加载单个 skill

        Args:
            skill_name: skill 目录名（如 "locator_best_practices"）

        Returns:
            Skill 实例

        Raises:
            FileNotFoundError: skill 不存在
        """
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise FileNotFoundError(
                f"Skill not found: {skill_path}\n"
                f"Available skills: {self.list_available_skills()}"
            )

        content = skill_path.read_text(encoding="utf-8")
        return Skill(name=skill_name, content=content, path=skill_path)

    def load_skills(self, skill_names: List[str]) -> List[Skill]:
        """
        批量加载多个 skills

        Args:
            skill_names: skill 名称列表

        Returns:
            Skill 实例列表
        """
        return [self.load_skill(name) for name in skill_names]

    def list_available_skills(self) -> List[str]:
        """
        列出所有可用的 skills

        Returns:
            skill 名称列表（排序）
        """
        skills = []
        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        return sorted(skills)


class SkillsMiddleware:
    """Skills 中间件 - 将 skills 注入到 Agent 的 system prompt"""

    def __init__(self, skills: List[Skill]):
        self.skills = skills

    def build_skills_section(self) -> str:
        """
        构建 skills 部分的 prompt

        Returns:
            组合后的 skills 文本
        """
        if not self.skills:
            return ""

        sections = []
        sections.append("# Available Skills\n")
        sections.append("You have access to the following specialized knowledge:\n")

        for skill in self.skills:
            sections.append(f"\n---\n")
            sections.append(skill.content)

        return "\n".join(sections)

    def inject_into_prompt(self, base_prompt: str) -> str:
        """
        将 skills 注入到基础 prompt 中

        Args:
            base_prompt: 基础 system prompt

        Returns:
            注入 skills 后的完整 prompt
        """
        skills_section = self.build_skills_section()

        if not skills_section:
            return base_prompt

        # 在 base_prompt 后面追加 skills section
        return f"{base_prompt}\n\n{skills_section}"


# =============================================================================
# 便捷函数（Global API）
# =============================================================================

# 全局加载器实例
_loader = SkillsLoader()


def load_skill(skill_name: str) -> Skill:
    """
    便捷函数：加载单个 skill

    Args:
        skill_name: skill 名称

    Returns:
        Skill 实例
    """
    return _loader.load_skill(skill_name)


def load_skills(skill_names: List[str]) -> List[Skill]:
    """
    便捷函数：批量加载 skills

    Args:
        skill_names: skill 名称列表

    Returns:
        Skill 实例列表
    """
    return _loader.load_skills(skill_names)


def list_available_skills() -> List[str]:
    """
    便捷函数：列出可用 skills

    Returns:
        skill 名称列表
    """
    return _loader.list_available_skills()


def create_skills_middleware(skill_names: List[str]) -> SkillsMiddleware:
    """
    便捷函数：创建 skills 中间件

    Args:
        skill_names: 要加载的 skill 名称列表

    Returns:
        SkillsMiddleware 实例
    """
    skills = load_skills(skill_names)
    return SkillsMiddleware(skills)


__all__ = [
    "Skill",
    "SkillsLoader",
    "SkillsMiddleware",
    "load_skill",
    "load_skills",
    "list_available_skills",
    "create_skills_middleware",
]
