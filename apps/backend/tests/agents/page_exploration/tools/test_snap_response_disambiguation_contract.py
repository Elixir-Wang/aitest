"""Step 3 接缝修复红测试：snap 响应契约（ancestor_chain 版本）。

契约：
1. snap 响应每个 element 必须有 sibling_count（整页面同 name+role 出现次数）
2. sibling_count > 1 时 is_ambiguous = True（LLM 知道该用 chain 容器）
3. snap 响应每个 element 必须有 ancestor_chain（来自 observation 的 DOM 祖先链）
4. snap 响应顶层必须有 match_groups（按 (name, role) 分组的所有候选列表），
   click 失败时 LLM 能看到全 3 个候选分别在哪
5. click 失败响应在 locator_not_unique 时必须枚举匹配元素列表
"""
from unittest.mock import patch

import pytest

from app.agents.page_exploration.playwright.schemas import (
    AccessibilityNodeInfo,
    ElementInfo,
    SnapshotResult,
)


def _observation_with_3_creates(*, ancestor_chain_for_second: list = None):
    """模拟 observation：3 个同名"创建"button，第 2 个带 ancestor_chain（表示在 popover 内）"""
    return {
        "observation_id": "obs-000001",
        "url": "https://example.com/workspace",
        "title": "Workspace",
        "page_text_summary": "Test.",
        "elements": [
            {
                "element_id": "obs-000001.el-001",
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": False, "match_count": 3},
                },
                "fallback_selector": None,
                "visible": True,
                "ancestor_chain": [],
            },
            {
                "element_id": "obs-000001.el-002",
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": False, "match_count": 3},
                },
                "fallback_selector": None,
                "visible": True,
                "ancestor_chain": ancestor_chain_for_second or [],
            },
            {
                "element_id": "obs-000001.el-003",
                "role": "button",
                "role_source": "native",
                "name": "创建",
                "text": "创建",
                "action_type": "click",
                "primary_selector": {
                    "kind": "role", "role": "button", "name": "创建",
                    "code": "page.getByRole('button', { name: '创建' })",
                    "verification": {"checked": True, "unique": False, "match_count": 3},
                },
                "fallback_selector": None,
                "visible": True,
                "ancestor_chain": [],
            },
        ],
        "accessibility_tree": [],
        "visible_text_blocks": [],
    }


@pytest.fixture
def patched_snapshot():
    """patch 掉浏览器依赖，直接给定 observation"""
    observation = _observation_with_3_creates(
        ancestor_chain_for_second=[{"role": "popover", "name": ""}]
    )

    with patch(
        "app.agents.page_exploration.tools.extraction_tools.snapshot_with_runtime_context",
        return_value=_to_snapshot_result(observation),
    ):
        yield observation


def _to_snapshot_result(obs):
    return SnapshotResult(
        observation_id=obs["observation_id"],
        url=obs["url"],
        title=obs["title"],
        elements=[_to_element_info(e) for e in obs["elements"]],
        accessibility_tree=[AccessibilityNodeInfo(**n) for n in obs["accessibility_tree"]],
        visible_text_blocks=obs["visible_text_blocks"],
    )


def _to_element_info(e):
    return ElementInfo(
        element_id=e["element_id"],
        role=e["role"],
        role_source=e.get("role_source", ""),
        name=e["name"],
        text=e.get("text"),
        action_type=e.get("action_type", ""),
        primary_selector=e.get("primary_selector"),
        fallback_selector=e.get("fallback_selector"),
        visible=e.get("visible", True),
        ancestor_chain=e.get("ancestor_chain") or [],
    )


# ---------- Step A: sibling_count / is_ambiguous ----------

def test_snap_response_includes_sibling_count_per_element(patched_snapshot):
    """snap 响应每个 element 必须有 sibling_count（同 name+role 全页面出现次数）。

    当前 bug：verification.unique 只验证单元素 DOM 位置唯一，不验证同 name+role
    在整页是否唯一。LLM 看到 unique=true 就放心写 getByRole，结果 Playwright
    严格模式抛 locator_not_unique。
    """
    from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool

    result = playwright_snap_tool.func()
    elements = result["elements"]
    assert len(elements) == 3
    # 3 个同名 button，每个 sibling_count 必须是 3
    for el in elements:
        assert "sibling_count" in el, f"缺少 sibling_count: {el}"
        assert el["sibling_count"] == 3, f"wrong sibling_count: {el}"
        assert el["is_ambiguous"] is True


# ---------- Step C: ancestor_chain 透传 ----------

def test_snap_response_passes_ancestor_chain_from_element_info(patched_snapshot):
    """每个 element 必须保留 ancestor_chain（DOM 祖先链）"""
    from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool

    result = playwright_snap_tool.func()
    elements = result["elements"]
    # 第 2 个 element 设置了 ancestor_chain=[{"role": "popover", "name": ""}]
    assert elements[1].get("ancestor_chain") == [{"role": "popover", "name": ""}], (
        f"ancestor_chain 透传丢失: {elements[1]}"
    )
    # 第 1、3 个没有 popover ancestor_chain，context_hint 应为 "main"
    for idx in [0, 2]:
        chain = elements[idx].get("ancestor_chain") or []
        overlay_roles = {"popover", "dialog", "alertdialog", "menu", "tooltip"}
        assert not any(a.get("role") in overlay_roles for a in chain)


# ---------- runtime element identity ----------

def test_snap_response_exposes_runtime_ids_and_verified_locator_metadata(patched_snapshot):
    from app.agents.page_exploration.tools.extraction_tools import playwright_snap_tool

    result = playwright_snap_tool.func()
    assert result["observation_id"] == "obs-000001"
    assert [item["element_id"] for item in result["elements"]] == [
        "obs-000001.el-001", "obs-000001.el-002", "obs-000001.el-003",
    ]
    assert "match_groups" not in result
    assert all("primary_selector" in item for item in result["elements"])
    assert all(
        item["primary_selector"]["verification"]["checked"] is True
        for item in result["elements"]
    )
