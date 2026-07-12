"""Step 2 接缝修复红测试：SnapshotResult/ElementInfo schema ancestor_chain 字段。

回归 bug：observePage 用硬编码选择器枚举 dialog 容器（缺 popover），导致 popover 内
元素无法被正确归属。

修复方案：ElementInfo 用 ancestor_chain（元素 DOM 祖先链）替代 dialog_id，
SnapshotResult 移除 dialogs / active_dialog_id（不再需要枚举层）。

本测试断言 schema 应该接收并保留 ancestor_chain 信息。
"""
import pytest
from app.agents.page_exploration.playwright.schemas import (
    ElementInfo,
    SnapshotResult,
)


def test_snapshot_result_has_elements_field():
    """SnapshotResult 必须有 elements 字段。"""
    snapshot = SnapshotResult(
        url="https://example.com/",
        title="Demo",
        elements=[],
    )
    assert hasattr(snapshot, "elements")
    assert snapshot.elements == []


def test_element_info_has_ancestor_chain_field():
    """ElementInfo 必须能接收 ancestor_chain 字段（popover/dialog/menu 等 DOM 上下文）。"""
    el = ElementInfo(
        element_id="obs-1.el-1",
        role="button",
        role_source="accessibility_tree",
        name="确认",
        text="确认",
        action_type="click",
        visible=True,
        ancestor_chain=[
            {"role": "popover", "name": ""},
            {"role": "div", "name": ""},
        ],
    )
    assert el.ancestor_chain == [
        {"role": "popover", "name": ""},
        {"role": "div", "name": ""},
    ]


def test_element_info_ancestor_chain_default_to_empty_list():
    """ancestor_chain 缺省值必须是空 list（非 overlay 元素不写这个字段）。"""
    el = ElementInfo(
        element_id="obs-1.el-1",
        role="button",
        role_source="accessibility_tree",
        name="发布",
        text="发布",
        action_type="click",
        visible=True,
    )
    assert el.ancestor_chain == []


def test_element_info_ancestor_chain_multiple_levels():
    """ancestor_chain 支持多层（popover > section > div）。"""
    el = ElementInfo(
        element_id="obs-1.el-1",
        role="button",
        role_source="native",
        name="删除",
        action_type="click",
        visible=True,
        ancestor_chain=[
            {"role": "menu", "name": ""},
            {"role": "section", "name": "操作区"},
            {"role": "div", "name": ""},
        ],
    )
    assert len(el.ancestor_chain) == 3
    assert el.ancestor_chain[0]["role"] == "menu"
