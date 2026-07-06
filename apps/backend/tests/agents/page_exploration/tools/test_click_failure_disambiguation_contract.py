"""Click 失败响应契约：locator_not_unique 时必须告诉 LLM 怎么消歧。

回归 bug：今早 session_62cdb1a0 click 失败时 error 只是 "Locator matched 3 elements: ..."
LLM 看不到 3 个匹配分别在哪，只能猜 nth-of-type / 容器。

修复契约：locator_not_unique 错误时 summary 必须：
1. 说明 N 个匹配存在
2. 提示 LLM 用 snap 响应里的 match_groups[(name, role)].candidates 列表对照消歧
3. 列举建议的 chain 模式（容器 filter）
"""
import pytest
from app.agents.page_exploration.tools.runtime_context import _parse_action_result


def test_locator_not_unique_summary_suggests_match_groups_lookup():
    """locator_not_unique 失败时 summary 必须提示 LLM 用 match_groups 查候选。"""
    action_result = {
        "success": False,
        "effective_locator": "page.getByRole('button', { name: '创建' })",
        "failure": {
            "error_type": "locator_not_unique",
            "summary": "Locator matched 3 elements.",
            "raw": "Locator matched 3 elements: page.getByRole('button', { name: '创建' })",
        },
    }
    parsed = _parse_action_result(
        action_result,
        raw_expr="page.getByRole('button', { name: '创建' })",
        default_error="Locator did not resolve",
    )
    summary = parsed["failure"].summary
    # 修复后 summary 必须包含指引：让 LLM 查 match_groups 而不是瞎猜 nth
    assert "match_groups" in summary or "再次 snap" in summary or "filter" in summary.lower(), (
        f"locator_not_unique summary 没指引 LLM 消歧: {summary!r}"
    )


def test_locator_not_unique_summary_includes_match_count():
    """locator_not_unique summary 必须报告实际匹配数（让 LLM 量化歧义程度）。"""
    action_result = {
        "success": False,
        "effective_locator": "page.getByRole('button', { name: '创建' })",
        "failure": {
            "error_type": "locator_not_unique",
            "summary": "Locator matched 3 elements.",
            "raw": "Locator matched 3 elements: page.getByRole('button', { name: '创建' })",
        },
    }
    parsed = _parse_action_result(
        action_result,
        raw_expr="page.getByRole('button', { name: '创建' })",
        default_error="",
    )
    summary = parsed["failure"].summary
    # summary 必须包含具体数字 (3) 让 LLM 知道歧义程度
    assert "3" in summary, f"summary 缺匹配数字: {summary!r}"


def test_locator_not_unique_failure_keeps_raw_for_debug():
    """failure 对象的 raw 字段保留原始 Playwright 错误（用于 debug）。"""
    action_result = {
        "success": False,
        "effective_locator": "page.getByRole('button', { name: '创建' })",
        "failure": {
            "error_type": "locator_not_unique",
            "summary": "Locator matched 3 elements.",
            "raw": "Locator matched 3 elements: page.getByRole('button', { name: '创建' })",
        },
    }
    parsed = _parse_action_result(
        action_result,
        raw_expr="page.getByRole('button', { name: '创建' })",
        default_error="",
    )
    assert "Locator matched 3 elements" in parsed["failure"].raw


def test_other_error_types_unchanged():
    """非 locator_not_unique 错误的 summary 不应被强制追加 match_groups 提示。"""
    action_result = {
        "success": False,
        "effective_locator": "page.locator('body').press('Escape')",
        "failure": {
            "error_type": "action_failed",
            "summary": "Unsupported locator: page.locator('body').press('Escape')",
            "raw": "Unsupported locator: page.locator('body').press('Escape')",
        },
    }
    parsed = _parse_action_result(
        action_result,
        raw_expr="page.locator('body').press('Escape')",
        default_error="",
    )
    # action_failed 不变（保持原文）
    assert "match_groups" not in parsed["failure"].summary
    assert "press" in parsed["failure"].raw  # 原始错误保留