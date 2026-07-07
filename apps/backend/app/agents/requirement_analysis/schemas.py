"""需求分析数据结构定义"""

from typing import Literal

from pydantic import BaseModel, Field


# ==================== 新的数据结构（核心）====================

class RequirementInput(BaseModel):
    """需求分析输入"""
    requirement_name: str = Field(..., description="需求名称")
    requirement_content: str = Field(..., description="主需求内容")
    auxiliary_docs: list[str] = Field(default_factory=list, description="辅助文档列表")


class RequirementUnderstanding(BaseModel):
    """需求理解（9个标准章节）"""
    background: str = Field(..., description="1. 需求背景")
    goals: str = Field(..., description="2. 目标与价值")
    users: str = Field(..., description="3. 用户角色与使用场景")
    scope: str = Field(..., description="4. 功能范围")
    flow: str = Field(..., description="5. 业务流程")
    states: str = Field(..., description="6. 状态流转")
    rules: str = Field(..., description="7. 业务规则")
    ui: str = Field(..., description="8. 页面与交互")
    data: str = Field(..., description="9. 数据与系统交互")


class ClarificationItem(BaseModel):
    """单个澄清问题"""
    id: str = Field(..., pattern=r"^clar-\d{3}$", description="问题ID，如 clar-001")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(..., description="优先级")
    module: str = Field(..., min_length=1, description="模块/对象名称")
    question: str = Field(..., min_length=1, description="具体的澄清问题")
    option_a: str = Field(..., min_length=1, description="推荐答案 A（最可能的答案）")
    option_b: str = Field(..., min_length=1, description="推荐答案 B（次可能的答案）")
    source_excerpt: str = Field(default="", description="问题来源的原文片段（可选）")
    impact: str = Field(..., min_length=1, description="该问题的影响说明")


class RequirementAnalysisResult(BaseModel):
    """需求分析完整结果"""
    understanding: RequirementUnderstanding = Field(..., description="需求理解")
    clarifications: list[ClarificationItem] = Field(
        min_length=1,
        description=(
            "澄清问题列表。任何需求文档都必须至少生成 1 条澄清问题。"
            "如果 LLM 主观判断'没有不明确点'，应优先列入低优先级（P3）"
            "而不是省略。"
        ),
    )

    @property
    def status(self) -> Literal["completed", "needs_clarification"]:
        """根据是否有澄清问题自动判断状态"""
        return "needs_clarification" if self.clarifications else "completed"

    def to_understanding_markdown(self) -> str:
        """转换为需求理解 Markdown"""
        u = self.understanding
        return f"""# 需求理解

## 1. 需求背景
{u.background}

## 2. 目标与价值
{u.goals}

## 3. 用户角色与使用场景
{u.users}

## 4. 功能范围
{u.scope}

## 5. 业务流程
{u.flow}

## 6. 状态流转
{u.states}

## 7. 业务规则
{u.rules}

## 8. 页面与交互
{u.ui}

## 9. 数据与系统交互
{u.data}
"""

    def to_clarification_markdown(self) -> str:
        """转换为待澄清 Markdown"""
        if not self.clarifications:
            return "# 待澄清问题\n\n暂无待澄清问题。"

        lines = ["# 待澄清问题\n"]
        lines.append("| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |")
        lines.append("|-------|----------|---------|--------|--------|------|")

        for item in self.clarifications:
            lines.append(
                f"| {item.priority} | {item.module} | {item.question} | "
                f"{item.option_a} | {item.option_b} | {item.impact} |"
            )

        return "\n".join(lines)


__all__ = [
    "RequirementInput",
    "RequirementUnderstanding",
    "ClarificationItem",
    "RequirementAnalysisResult",
]
