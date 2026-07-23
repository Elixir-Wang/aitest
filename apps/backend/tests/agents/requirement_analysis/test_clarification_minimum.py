"""回归测试：澄清问题非空约束与内容质量边界。

背景：result.json 里出现 status=completed + clarifications=[] + "暂无待澄清问题"
的产物。schema 继续强制至少一条，skill 同时要求问题可追溯、可裁决并能转化为用例，
避免模型为了达到固定数量而生成无来源问题。

本测试覆盖三层防御：
1. Skill 明确 schema 至少一条，并禁止凑数
2. clarification reference 强制来源和用例转化准入
3. RequirementAnalysisResult.clarifications schema 保持 min_length >= 1
   （pydantic 解析时强制非空）

按 TDD：先看到这些断言失败 → 再修复 SKILL.md / references / schemas。
"""
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.requirement_analysis.schemas import (
    ClarificationItem,
    RequirementAnalysisResult,
)


# 测试在不同 cwd 下都能稳定找到 skill 目录（pytest 可能从 apps/backend 或仓库根启动）
_CANDIDATE_ROOTS = [
    Path(__file__).resolve().parents[3],  # apps/backend（tests/agents/<x>/test.py → 3 级 parent）
    Path.cwd(),
]
SKILL_DIR = next(
    (
        root / "app" / "agents" / "requirement_analysis" / "skills" / "requirements-analysis"
        for root in _CANDIDATE_ROOTS
        if (root / "app" / "agents" / "requirement_analysis" / "skills" / "requirements-analysis" / "SKILL.md").exists()
    ),
    None,
)
assert SKILL_DIR is not None, (
    "找不到 skill 目录；已尝试: "
    + ", ".join(str(r) for r in _CANDIDATE_ROOTS)
)
SKILL_MD = SKILL_DIR / "SKILL.md"
CLARIFICATION_MD = SKILL_DIR / "references" / "clarification.md"

# ==================== 1. SKILL.md 必须兼顾非空与质量 ====================

def test_skill_md_requires_minimum_clarifications() -> None:
    """SKILL.md 必须要求至少一条，但不得要求凑固定数量。"""
    assert SKILL_MD.exists(), f"SKILL.md 不存在: {SKILL_MD}"
    content = SKILL_MD.read_text(encoding="utf-8")
    assert "至少输出 1 条" in content
    assert "不得为了凑数量" in content
    assert "至少生成 3 条" not in content


# ==================== 2. clarification reference 必须包含质量准入 ====================

def test_clarification_reference_requires_minimum_clarifications() -> None:
    """Reference 必须要求来源和用例转化，禁止机械凑数。"""
    assert CLARIFICATION_MD.exists(), f"clarification.md 不存在: {CLARIFICATION_MD}"
    content = CLARIFICATION_MD.read_text(encoding="utf-8")
    assert "原文事实 → 具体缺口/歧义/冲突" in content
    assert "确认答案后至少能形成一个 Given/When/Then 用例" in content
    assert "不得为了凑数量" in content


# ==================== 3. schema 必须强制 clarifications 非空 ====================

def test_clarifications_field_has_min_length_constraint() -> None:
    """RequirementAnalysisResult.clarifications 必须在 schema 层强制非空。"""
    json_schema = RequirementAnalysisResult.model_json_schema()
    clarifications_schema = json_schema["properties"]["clarifications"]

    # pydantic 的 min_length 会映射到 array schema 的 minItems
    min_items = clarifications_schema.get("minItems")
    assert min_items is not None and min_items >= 1, (
        f"RequirementAnalysisResult.clarifications 缺少 min_length 约束。"
        f"当前 schema: {clarifications_schema}"
    )


def test_clarifications_empty_list_fails_validation() -> None:
    """空 clarifications 列表必须被 pydantic 拒绝（不再静默放过）。"""
    with pytest.raises(ValidationError):
        RequirementAnalysisResult(understanding_markdown="# 需求理解", clarifications=[])


def test_clarifications_singleton_list_passes_validation() -> None:
    """至少 1 条澄清问题必须能通过 schema 验证。"""
    item = ClarificationItem(
        id="clar-001",
        priority="P0",
        module="登录",
        question="测试问题？",
        option_a="选项 A",
        option_b="选项 B",
        impact="影响说明",
    )
    result = RequirementAnalysisResult(understanding_markdown="# 需求理解", clarifications=[item])
    assert len(result.clarifications) == 1


def test_clarification_impact_schema_is_qa_oriented() -> None:
    """impact 字段必须引导模型输出 QA 视角的测试影响，而不是研发影响。"""
    description = str(ClarificationItem.model_fields["impact"].description)

    assert "测试" in description
    assert "开发" not in description


def test_clarification_markdown_uses_test_impact_header() -> None:
    """待澄清 Markdown 表格应明确展示为测试影响。"""
    item = ClarificationItem(
        id="clar-001",
        priority="P0",
        module="登录",
        question="账号冻结状态下是否允许登录？",
        option_a="不允许登录并提示账号已冻结",
        option_b="允许登录但限制部分功能",
        impact="影响冻结账号场景的测试用例设计和权限断言。",
    )
    result = RequirementAnalysisResult(understanding_markdown="# 需求理解", clarifications=[item])

    markdown = result.to_clarification_markdown()

    assert "| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 测试影响 |" in markdown
    assert "| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |" not in markdown
