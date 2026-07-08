"""回归测试：澄清问题数量约束（防御 deepseek-v4-flash 输出空 clarifications）

背景：result.json 里出现 status=completed + clarifications=[] + "暂无待澄清问题"
的产物。原因是 SKILL.md + schema 都没有"必须至少 N 条澄清"的硬约束，LLM
（实际跑的是 deepseek-v4-flash）会按"原文都说明清楚了"自我判断，输出空数组。

本测试覆盖三层防御：
1. Skill 中 SKILL.md 必须包含"至少 N 条"的明确数量指令
2. references/clarification.md 必须包含"至少 N 条"的明确数量指令
3. RequirementAnalysisResult.clarifications schema 必须有 min_length >= 1 约束
   （pydantic 解析时强制非空）

按 TDD：先看到这些断言失败 → 再修复 SKILL.md / references / schemas。
"""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.requirement_analysis.schemas import (
    ClarificationItem,
    RequirementAnalysisResult,
    RequirementUnderstanding,
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

# 至少澄清问题数量门槛：所有正常需求文档都必须生成不少于这个数量的澄清问题
MIN_CLARIFICATIONS = 3


# ==================== 1. SKILL.md 必须包含数量约束 ====================

def test_skill_md_requires_minimum_clarifications() -> None:
    """SKILL.md 必须明确写出'至少 N 条澄清问题'的硬约束。"""
    assert SKILL_MD.exists(), f"SKILL.md 不存在: {SKILL_MD}"
    content = SKILL_MD.read_text(encoding="utf-8")
    # 接受中英文常见写法
    pattern = re.compile(
        r"(至少|不少于|最少|≥\s*\d|>=?\s*\d|\bat\s+least\s+\d)",
        re.IGNORECASE,
    )
    assert pattern.search(content), (
        f"SKILL.md 必须包含'至少 N 条澄清问题'的数量硬约束，"
        f"否则 LLM（deepseek-v4-flash）会输出空 clarifications。\n"
        f"当前 SKILL.md 末尾:\n{content[-800:]}"
    )
    # 必须显式提到 MIN_CLARIFICATIONS 这个数值
    assert str(MIN_CLARIFICATIONS) in content or str(MIN_CLARIFICATIONS - 1) in content, (
        f"SKILL.md 必须显式提到具体数量（建议 {MIN_CLARIFICATIONS} 条），"
        f"不能只写'若干'、'一些'。"
    )


# ==================== 2. references/clarification.md 必须包含数量约束 ====================

def test_clarification_reference_requires_minimum_clarifications() -> None:
    """references/clarification.md 也必须包含'至少 N 条'的数量指令。"""
    assert CLARIFICATION_MD.exists(), f"clarification.md 不存在: {CLARIFICATION_MD}"
    content = CLARIFICATION_MD.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(至少|不少于|最少|≥\s*\d|>=?\s*\d|\bat\s+least\s+\d)",
        re.IGNORECASE,
    )
    assert pattern.search(content), (
        f"references/clarification.md 必须包含'至少 N 条澄清问题'的数量硬约束。"
    )


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
    understanding = RequirementUnderstanding(
        background="背景",
        goals="目标",
        users="用户",
        scope="范围",
        flow="流程",
        states="状态",
        rules="规则",
        ui="界面",
        data="数据",
    )

    with pytest.raises(ValidationError):
        RequirementAnalysisResult(understanding=understanding, clarifications=[])


def test_clarifications_singleton_list_passes_validation() -> None:
    """至少 1 条澄清问题必须能通过 schema 验证。"""
    understanding = RequirementUnderstanding(
        background="背景",
        goals="目标",
        users="用户",
        scope="范围",
        flow="流程",
        states="状态",
        rules="规则",
        ui="界面",
        data="数据",
    )
    item = ClarificationItem(
        id="clar-001",
        priority="P0",
        module="登录",
        question="测试问题？",
        option_a="选项 A",
        option_b="选项 B",
        impact="影响说明",
    )
    result = RequirementAnalysisResult(understanding=understanding, clarifications=[item])
    assert len(result.clarifications) == 1


def test_clarification_impact_schema_is_qa_oriented() -> None:
    """impact 字段必须引导模型输出 QA 视角的测试影响，而不是研发影响。"""
    description = str(ClarificationItem.model_fields["impact"].description)

    assert "测试" in description
    assert "开发" not in description


def test_clarification_markdown_uses_test_impact_header() -> None:
    """待澄清 Markdown 表格应明确展示为测试影响。"""
    understanding = RequirementUnderstanding(
        background="背景",
        goals="目标",
        users="用户",
        scope="范围",
        flow="流程",
        states="状态",
        rules="规则",
        ui="界面",
        data="数据",
    )
    item = ClarificationItem(
        id="clar-001",
        priority="P0",
        module="登录",
        question="账号冻结状态下是否允许登录？",
        option_a="不允许登录并提示账号已冻结",
        option_b="允许登录但限制部分功能",
        impact="影响冻结账号场景的测试用例设计和权限断言。",
    )
    result = RequirementAnalysisResult(understanding=understanding, clarifications=[item])

    markdown = result.to_clarification_markdown()

    assert "| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 测试影响 |" in markdown
    assert "| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |" not in markdown
