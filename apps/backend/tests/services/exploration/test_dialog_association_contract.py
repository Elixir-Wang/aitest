"""Step 3 接缝修复：element ↔ dialog 关联透传。

回归 bug：observePage 收集的 facts.dialogs 列表（第 1000-1007 行 of browser-session.mjs）
没有把 element 归属到 dialog，导致弹窗内元素和主页面元素无法区分。

本测试断言 _snapshot_elements_for_artifact 在收到带 dialog_id 的 observation 时
正确把 dialog_id 透传到 artifact element，让外部脚本能根据 dialog_id 区分元素归属。
"""
import pytest
from app.services.exploration.page_exploration_service import (
    _snapshot_elements_for_artifact,
)


def test_dialog_element_passes_dialog_id_through_to_artifact():
    """弹窗内的 button 必须带 dialog_id 字段。"""
    observation_elements = [
        # 主页面上的"发布"按钮（无 dialog 归属）
        {
            "id": "el-1",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "发布",
            "text": "发布",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role", "role": "button", "name": "发布",
                "code": "getByRole('button', { name: '发布' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            # 注意：没 dialog_id 字段
        },
        # 弹窗内的"确认"按钮（dialog 归属 dialog-001）
        {
            "id": "el-2",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "确认",
            "text": "确认",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role", "role": "button", "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "dialog_id": "dialog-001",
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)

    assert len(artifact_elements) == 2

    # el-1（主页面发布按钮）：不应该有 dialog_id
    main_page_btn = next(e for e in artifact_elements if e["id"] == "el-1")
    assert "dialog_id" not in main_page_btn, (
        f"主页面元素不应有 dialog_id: {main_page_btn}"
    )

    # el-2（弹窗确认按钮）：必须透传 dialog_id
    dialog_btn = next(e for e in artifact_elements if e["id"] == "el-2")
    assert dialog_btn.get("dialog_id") == "dialog-001", (
        f"弹窗内元素 dialog_id 透传失败: {dialog_btn}"
    )


def test_dialog_id_distinguishes_same_named_elements_across_dialogs():
    """两个 dialog 各有一个"确认"按钮，必须能用 dialog_id 区分。"""
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
                "kind": "role", "role": "button", "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 2},
            },
            "fallback_selector": None,
            "dialog_id": "dialog-A",
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
                "kind": "role", "role": "button", "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 2},
            },
            "fallback_selector": None,
            "dialog_id": "dialog-B",
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)

    el_a = next(e for e in artifact_elements if e["id"] == "el-1")
    el_b = next(e for e in artifact_elements if e["id"] == "el-2")
    assert el_a["dialog_id"] == "dialog-A"
    assert el_b["dialog_id"] == "dialog-B"
    assert el_a["dialog_id"] != el_b["dialog_id"], (
        "同名按钮在不同 dialog 必须有不同 dialog_id，否则外部脚本无法消歧"
    )


def test_dialog_id_handles_empty_string_as_missing():
    """空字符串 dialog_id 应被视为无 dialog 归属（不写字段）。"""
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
                "kind": "role", "role": "button", "name": "取消",
                "code": "getByRole('button', { name: '取消' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
            "dialog_id": "",  # 空字符串
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    el = artifact_elements[0]
    # 空字符串 dialog_id 不应该写到 artifact（保持 schema 干净）
    assert "dialog_id" not in el or el["dialog_id"] in (None, ""), (
        f"空字符串 dialog_id 处理不当: {el}"
    )
