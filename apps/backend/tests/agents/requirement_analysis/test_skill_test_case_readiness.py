"""Contract tests for test-case-oriented requirement-analysis guidance."""

from pathlib import Path


SKILL_DIR = (
    Path(__file__).resolve().parents[3]
    / "app/agents/requirement_analysis/skills/requirements-analysis"
)


def _read(relative_path: str) -> str:
    return (SKILL_DIR / relative_path).read_text(encoding="utf-8")


def test_skill_defines_evidence_bound_mermaid_triggers() -> None:
    content = _read("SKILL.md")

    assert "至少 3 个已确认步骤" in content
    assert "stateDiagram-v2" in content
    assert "sequenceDiagram" in content
    assert "图表只表达已确认事实" in content
    assert "即使 Mermaid 无法渲染" in content


def test_understanding_is_organized_for_downstream_test_cases() -> None:
    content = _read("references/understanding.md")

    assert "用例可理解性基线" in content
    assert "角色与权限" in content
    assert "可观察结果" in content
    assert "状态/数据变化" in content
    assert "不把待澄清问题画成已确认流程" in content


def test_clarification_requires_traceable_test_decisions() -> None:
    content = _read("references/clarification.md")

    assert "原文事实 → 具体缺口/歧义/冲突" in content
    assert "确认答案后至少能形成一个 Given/When/Then 用例" in content
    assert "不得为了凑数量" in content
    assert "采用乐观锁还是分布式锁" in content


def test_skill_no_longer_requires_three_questions() -> None:
    skill = _read("SKILL.md")
    clarification = _read("references/clarification.md")

    assert "至少生成 3 条" not in skill
    assert "至少 3 条澄清问题" not in clarification
    assert "至少输出 1 条" in skill
