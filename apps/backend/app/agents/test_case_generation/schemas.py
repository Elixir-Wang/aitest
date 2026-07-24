"""测试用例生成数据结构定义"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.agents.rejected_case_search.schemas import RejectedCaseReference


# ==================== 新的数据结构（核心）====================

class TestCaseStep(BaseModel):
    """单个测试步骤及对应预期"""

    action: str = Field(..., min_length=1, description="测试动作")
    expected_result: str = Field(..., min_length=1, description="该步骤完成后的可验证预期结果")

    @field_validator("action", "expected_result", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TestCaseGenerationInput(BaseModel):
    """测试用例生成输入"""
    requirement_name: str = Field(..., description="需求名称")
    requirement_content: str = Field(..., description="最终需求内容（需求理解）")
    generation_scope: str = Field(default="", description="生成范围（可选，如：只生成登录模块的测试用例）")
    test_points: list[dict] = Field(default_factory=list, description="当前最终需求版本下的测试点")
    rejected_case_references: list[RejectedCaseReference] = Field(
        default_factory=list,
        description="Agentic Search 召回的历史不采纳用例引用",
    )


class TestCase(BaseModel):
    """单个测试用例"""
    id: str = Field(..., pattern=r"^tc-\d{3}$", description="测试用例ID，如 tc-001")
    module: str = Field(..., min_length=1, description="所属模块")
    title: str = Field(..., min_length=1, description="测试用例标题")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(..., description="优先级")
    type: Literal["功能测试", "异常测试", "边界测试", "性能测试", "安全测试", "兼容测试"] = Field(
        ..., description="测试类型"
    )
    precondition: str = Field(default="", description="前置条件")
    steps: list[TestCaseStep] = Field(..., min_length=1, description="测试步骤及每步预期")
    expected_result: str = Field(..., min_length=1, description="整条用例的最终或汇总预期结果")
    test_data: str = Field(default="", description="测试数据")
    notes: str = Field(default="", description="备注")


class TestCaseModule(BaseModel):
    """测试用例模块"""
    module_name: str = Field(..., description="模块名称")
    test_cases: list[TestCase] = Field(..., description="该模块的测试用例列表")


class TestCaseGenerationResult(BaseModel):
    """测试用例生成完整结果"""
    summary: str = Field(..., description="测试用例集概述")
    total_count: int = Field(..., description="测试用例总数")
    modules: list[TestCaseModule] = Field(..., description="按模块组织的测试用例")

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            "# 测试用例集",
            "",
            f"## 概述",
            self.summary,
            "",
            f"**测试用例总数**: {self.total_count}",
            "",
        ]

        for module in self.modules:
            lines.append(f"## {module.module_name}")
            lines.append("")

            for tc in module.test_cases:
                lines.append(f"### {tc.id} - {tc.title}")
                lines.append("")
                lines.append(f"- **优先级**: {tc.priority}")
                lines.append(f"- **测试类型**: {tc.type}")

                if tc.precondition:
                    lines.append(f"- **前置条件**: {tc.precondition}")

                lines.append("")
                lines.append("**测试步骤**:")
                for i, step in enumerate(tc.steps, 1):
                    lines.append(f"{i}. {step.action}")
                    lines.append(f"   - 预期结果：{step.expected_result}")

                lines.append("")
                lines.append(f"**预期结果**: {tc.expected_result}")

                if tc.test_data:
                    lines.append("")
                    lines.append(f"**测试数据**: {tc.test_data}")

                if tc.notes:
                    lines.append("")
                    lines.append(f"**备注**: {tc.notes}")

                lines.append("")

        return "\n".join(lines)


__all__ = [
    "TestCaseStep",
    "TestCaseGenerationInput",
    "TestCase",
    "TestCaseModule",
    "TestCaseGenerationResult",
]
