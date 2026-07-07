"""Step 3 接缝修复：element ↔ dialog 关联透传（已重构为 ancestor_chain）。

回归 bug：observePage 用硬编码选择器枚举 dialog 容器，永远枚举不完。
修复方案：直接发 ancestor_chain（元素到 body 的 DOM 祖先路径），LLM 自己判断上下文。

本测试断言 _snapshot_elements_for_artifact 在收到带 ancestor_chain 的 observation 时
正确把 ancestor_chain 透传到 artifact element，让外部脚本能判断元素所在上下文。
"""
import pytest
from app.services.page_exploration.service import (
    _snapshot_elements_for_artifact,
)


def test_popover_element_passes_ancestor_chain_through_to_artifact():
    """popover 内的 button 必须带 ancestor_chain 字段。"""
    observation_elements = [
        # 主页面上的"发布"按钮（无 ancestor_chain）
        {
            "id": "el-1",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "发布",
            "text": "发布",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "发布",
                "code": "getByRole('button', { name: '发布' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
        },
        # popover 内的"确认"按钮
        {
            "id": "el-2",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "确认",
            "text": "确认",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "ancestor_chain": [
                {"role": "popover", "name": ""},
                {"role": "div", "name": ""},
            ],
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)

    assert len(artifact_elements) == 2

    # el-1（主页面发布按钮）：不应该有 ancestor_chain
    main_page_btn = next(e for e in artifact_elements if e["id"] == "el-1")
    assert "ancestor_chain" not in main_page_btn, (
        f"主页面元素不应有 ancestor_chain: {main_page_btn}"
    )

    # el-2（popover 确认按钮）：必须透传 ancestor_chain
    popover_btn = next(e for e in artifact_elements if e["id"] == "el-2")
    assert popover_btn.get("ancestor_chain") == [
        {"role": "popover", "name": ""},
        {"role": "div", "name": ""},
    ], f"popover 内元素 ancestor_chain 透传失败: {popover_btn}"


def test_ancestor_chain_distinguishes_same_named_elements_across_overlays():
    """两个 overlay 各有一个"确认"按钮，必须能用 ancestor_chain 区分。"""
    observation_elements = [
        {
            "id": "el-A",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "确认",
            "text": "确认",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "ancestor_chain": [{"role": "dialog", "name": "发布确认"}],
        },
        {
            "id": "el-B",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "确认",
            "text": "确认",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "ancestor_chain": [{"role": "menu", "name": ""}],
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)

    el_a = next(e for e in artifact_elements if e["name"] == "确认" and e.get("ancestor_chain") == [{"role": "dialog", "name": "发布确认"}])
    el_b = next(e for e in artifact_elements if e["name"] == "确认" and e.get("ancestor_chain") == [{"role": "menu", "name": ""}])
    # ancestor_chain 不同，外部脚本能据此区分
    assert el_a.get("ancestor_chain") == [{"role": "dialog", "name": "发布确认"}]
    assert el_b.get("ancestor_chain") == [{"role": "menu", "name": ""}]
    assert el_a.get("ancestor_chain") != el_b.get("ancestor_chain"), (
        "同名按钮在不同 overlay 必须有不同 ancestor_chain"
    )


def test_empty_ancestor_chain_not_written_to_artifact():
    """空 list ancestor_chain 应被视为无上下文归属（不写字段）。"""
    observation_elements = [
        {
            "id": "el-1",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "取消",
            "text": "取消",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "取消",
                "code": "getByRole('button', { name: '取消' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "ancestor_chain": [],
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    el = artifact_elements[0]
    assert "ancestor_chain" not in el, f"空 ancestor_chain 不应写到 artifact: {el}"
