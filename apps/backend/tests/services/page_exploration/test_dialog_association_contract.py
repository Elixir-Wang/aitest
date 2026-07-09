"""Step 3 接缝修复：element ↔ dialog 关联压缩为 automation context。

回归 bug：observePage 用硬编码选择器枚举 dialog 容器，永远枚举不完。
修复方案：采集端可发送 ancestor_chain（元素到 body 的 DOM 祖先路径），产物端只保留
UI 自动化需要的精简 context，避免 YAML 输出长祖先文本。

本测试断言 _snapshot_elements_for_artifact 在收到带 ancestor_chain 的 observation 时
正确提炼 container_role/container_name，让外部脚本能判断元素所在上下文。
"""
from app.services.page_exploration.service import (
    _snapshot_elements_for_artifact,
)


def test_popover_element_passes_compact_context_to_artifact():
    """popover 内的 button 必须带精简上下文字段，不输出完整 ancestor_chain。"""
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

    main_page_btn = next(e for e in artifact_elements if e["id"] == "el-1")
    assert "ancestor_chain" not in main_page_btn

    popover_btn = next(e for e in artifact_elements if e["id"] == "el-2")
    assert "ancestor_chain" not in popover_btn
    assert popover_btn["context"]["container_role"] == "popover"
    assert popover_btn["context"]["container_name"] == ""


def test_context_distinguishes_same_named_elements_across_overlays():
    """两个 overlay 各有一个"确认"按钮，必须能用 context 区分。"""
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

    el_a = next(e for e in artifact_elements if e["id"] == "el-A")
    el_b = next(e for e in artifact_elements if e["id"] == "el-B")
    assert el_a["context"]["container_role"] == "dialog"
    assert el_a["context"]["container_name"] == "发布确认"
    assert el_b["context"]["container_role"] == "menu"
    assert el_b["context"]["container_name"] == ""
    assert el_a["context"] != el_b["context"], "同名按钮在不同 overlay 必须有不同 context"


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
