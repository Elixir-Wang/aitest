"""Step 2 接缝修复红测试：SnapshotResult/ElementInfo schema 缺 dialog 字段。

回归 bug：observePage 返回的 dialogs 列表被 SnapshotResult schema 丢弃，
ElementInfo 缺 dialog_id（元素所属 dialog）字段。

本测试断言 schema 应该接收并保留 dialog 信息。
"""
import pytest
from app.agents.page_exploration.playwright.schemas import (
    ElementInfo,
    SnapshotResult,
    DialogInfo,
)


def test_snapshot_result_has_dialogs_field():
    """SnapshotResult 必须能接收 dialogs 列表（observePage 已经在收集）。"""
    snapshot = SnapshotResult(
        url="https://example.com/",
        title="Demo",
        elements=[],
        dialogs=[
            DialogInfo(id="dialog-001", title="确认要发布吗？", role="dialog"),
        ],
    )
    assert hasattr(snapshot, "dialogs"), "SnapshotResult 缺 dialogs 字段"
    assert len(snapshot.dialogs) == 1
    assert snapshot.dialogs[0].id == "dialog-001"
    assert snapshot.dialogs[0].title == "确认要发布吗？"


def test_snapshot_result_dialogs_default_to_empty_list():
    """dialogs 字段默认值必须是空 list（不报错，外部脚本能正常迭代）。"""
    snapshot = SnapshotResult(url="https://example.com/", title="x", elements=[])
    assert snapshot.dialogs == []


def test_element_info_has_dialog_id_field():
    """ElementInfo 必须能接收 dialog_id 字段（弹窗内元素归属）。"""
    el = ElementInfo(
        role="button",
        role_source="accessibility_tree",
        name="确认",
        text="确认",
        action_type="click",
        visible=True,
        dialog_id="dialog-001",
    )
    assert el.dialog_id == "dialog-001"


def test_element_info_dialog_id_optional():
    """dialog_id 缺省值必须是 None（非弹窗元素不写这个字段）。"""
    el = ElementInfo(
        role="button",
        role_source="accessibility_tree",
        name="发布",
        text="发布",
        action_type="click",
        visible=True,
    )
    assert el.dialog_id is None


def test_dialog_info_carries_role_for_specificity():
    """DialogInfo 携带 role 字段（区分 dialog/alertdialog 等）。"""
    d = DialogInfo(id="d-1", title="错误", role="alertdialog")
    assert d.role == "alertdialog"


def test_snapshot_result_active_dialog_id_field():
    """SnapshotResult 应记录当前 active dialog（影响 LLM 后续动作的 scope）。"""
    snapshot = SnapshotResult(
        url="https://example.com/",
        title="Demo",
        elements=[],
        active_dialog_id="dialog-001",
    )
    assert snapshot.active_dialog_id == "dialog-001"
