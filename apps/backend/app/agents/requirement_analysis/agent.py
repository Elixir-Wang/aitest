"""需求分析 Agent 定义（Middleware 版本）"""

from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.schemas import RequirementAnalysisResult
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware


def requirement_analysis_agent(
    model,
    load_references: bool = True,
    base_prompt: str | None = None,
):
    """
    创建需求分析 Agent（使用 Skill Middleware）

    架构：
    - 单一 Agent
    - 结构化输出（RequirementAnalysisResult）
    - 使用 SkillMiddleware 动态加载 SKILL.md 和 references/

    Args:
        model: LLM 模型实例
        load_references: 是否加载 references/ 下的参考文档（默认 True）
        base_prompt: 基础提示词（可选，会与 Skill 内容组合）

    Returns:
        配置好的需求分析 Agent
    """
    skill_middleware = SkillMiddleware(
        skill_path=Path(__file__).parent / "skills" / "requirements-analysis",
        load_references=load_references,
    )

    return create_agent(
        model=model,
        tools=[],
        system_prompt=base_prompt,
        middleware=[skill_middleware, InvalidToolCallRecoveryMiddleware()],
        response_format=ToolStrategy(RequirementAnalysisResult),
    )

