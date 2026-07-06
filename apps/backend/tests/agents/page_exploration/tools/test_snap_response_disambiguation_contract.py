"""Runtime contract: playwright_snap_tool 响应必须暴露歧义信息和 dialog 归属。

回归 bug：今早 session_62cdb1a0 4 次 click 失败（locator 命中 3 个），snap 响应里
虽然有 verification 字段，但只验证"这个元素自身 location 唯一"，不验证"同名同 role
在整页面只出现一次"——LLM 看到的是误报。click 失败时 error message 只说"匹配 3 个"，
不给匹配的元素列表，LLM 只能瞎猜 nth-of-type。

修复契约：
1. snap 响应每个 element 必须有 sibling_count（整页面同 name+role 出现次数）
2. sibling_count > 1 时 is_ambiguous = True（LLM 知道该用 chain 容器）
3. snap 响应每个 element 必须有 dialog_id（来自 observation 的 dialog 归属）
4. snap 响应顶层必须有 match_groups（按 (name, role) 分组的所有候选列表），
   click 失败时 LLM 能看到全 3 个候选分别在哪
5. click 失败响应在 locator_not_unique 时必须枚举匹配元素列表
"""
from unittest.mock import patch

import pytest

from app.agents.page_exploration.playwright.schemas import (
    AccessibilityNodeInfo,
    DialogInfo,
    ElementInfo,
    SnapshotResult,
)
from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool


def _observation_with_3_creates(*, dialog_id_for_second: str = ""):
    """模拟 observation：3 个同名"创建"button，第 2 个带 dialog_id"""
    return {
        "url": "https://example.com/workspace",
        "title": "Workspace",
        "page_text_summary": "Test.",
        "elements": [
            {
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                },
                "fallback_selector": None,
                "visible": True,
                "dialog_id": "",
            },
            {
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                },
                "fallback_selector": None,
                "visible": True,
                "dialog_id": dialog_id_for_second,  # 第 2 个可能在弹窗内
            },
            {
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                },
                "fallback_selector": None,
                "visible": True,
                "dialog_id": "",
            },
        ],
        "accessibility_tree": [],
        "visible_text_blocks": [],
    }


@pytest.fixture
def patched_snapshot():
    """patch 掉浏览器依赖，直接给定 observation"""
    observation = _observation_with_3_creates(dialog_id_for_second="confirm-modal")

    with patch(
        "app.agents.page_exploration.tools.extraction_tools.snapshot_with_runtime_context",
        return_value=_to_snapshot_result(observation),
    ):
        yield observation


def _to_snapshot_result(obs):
    return SnapshotResult(
        url=obs["url"],
        title=obs["title"],
        page_text_summary=obs["page_text_summary"],
        elements=[_to_element_info(e) for e in obs["elements"]],
        accessibility_tree=[AccessibilityNodeInfo(**n) for n in obs["accessibility_tree"]],
        visible_text_blocks=obs["visible_text_blocks"],
        dialogs=[DialogInfo(id="confirm-modal", title="确认发布", role="dialog")],
    )


def _to_element_info(e):
    return ElementInfo(
        role=e["role"],
        role_source=e.get("role_source", ""),
        name=e["name"],
        text=e.get("text"),
        action_type=e.get("action_type", ""),
        primary_selector=e.get("primary_selector"),
        fallback_selector=e.get("fallback_selector"),
        visible=e.get("visible", True),
        dialog_id=e.get("dialog_id") or None,
    )


# ---------- Step A: sibling_count / is_ambiguous ----------

def test_snap_response_includes_sibling_count_per_element(patched_snapshot):
    """snap 响应每个 element 必须有 sibling_count（同 name+role 全页面出现次数）。

    当前 bug：verification.unique 只验证单元素 DOM 位置唯一，不验证同 name+role
    在整页是否唯一。LLM 看到 unique=true 就放心写 getByRole，结果 Playwright
    严格模式命中 3 个。
    """
    result = playwright_snap_tool.func()
    elements = result["elements"]
    assert len(elements) == 3
    for el in elements:
        assert "sibling_count" in el, f"element 缺 sibling_count: {el}"
        assert el["sibling_count"] == 3, (
            f"3 个同 name+role 按钮，sibling_count 应为 3，实际: {el['sibling_count']}"
        )


def test_snap_response_marks_is_ambiguous_when_sibling_count_gt_1(patched_snapshot):
    """sibling_count > 1 时 is_ambiguous=True（LLM 用 chain 容器的信号）。"""
    result = playwright_snap_tool.func()
    for el in result["elements"]:
        assert "is_ambiguous" in el, f"element 缺 is_ambiguous: {el}"
        assert el["is_ambiguous"] is True, "3 个同名，is_ambiguous 必须为 True"


# ---------- Step C: dialog_id 透传 ----------

def test_snap_response_passes_dialog_id_from_element_info(patched_snapshot):
    """每个 element 必须保留 dialog_id（弹窗内元素归属）"""
    result = playwright_snap_tool.func()
    elements = result["elements"]
    # 第 2 个 element 设置了 dialog_id="confirm-modal"
    assert elements[1].get("dialog_id") == "confirm-modal", (
        f"dialog_id 透传丢失: {elements[1]}"
    )
    # 第 1、3 个没设置 dialog_id → 不应有字段（或者 None）
    assert elements[0].get("dialog_id") in (None, ""), (
        f"主页面元素不应有 dialog_id: {elements[0]}"
    )
    assert elements[2].get("dialog_id") in (None, ""), (
        f"主页面元素不应有 dialog_id: {elements[2]}"
    )


# ---------- Step A 进阶: match_groups 让 LLM 看到全部同名候选 ----------

def test_snap_response_includes_match_groups(patched_snapshot):
    """snap 响应顶层必须有 match_groups：按 (name, role) 分组的所有候选。

    让 LLM 一次性看到 3 个"创建"分别在哪（dialog/列表/头部），而不是猜容器。
    """
    result = playwright_snap_tool.func()
    assert "match_groups" in result, "snap 响应缺 match_groups"
    groups = result["match_groups"]
    # 找 ("创建", "button") 组
    creates = [g for g in groups if g.get("name") == "创建" and g.get("role") == "button"]
    assert len(creates) == 1, f"match_groups 应有一个 ('创建','button') 组：{groups}"
    create_group = creates[0]
    assert create_group["count"] == 3
    # 每个候选至少有 basic locator 信息
    candidates = create_group["candidates"]
    assert len(candidates) == 3
    for cand in candidates:
        assert "dialog_id" in cand
        assert "primary_selector_code" in cand or "primary_selector" in cand
