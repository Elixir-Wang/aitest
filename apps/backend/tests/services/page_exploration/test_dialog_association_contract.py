"""Overlay association stays compact and distinguishes same-name controls."""

from app.services.page_exploration.output_registry import _snapshot_elements_for_artifact


def _button(name: str, container: dict | None = None) -> dict:
    element = {
        "role": "button",
        "name": name,
        "action_type": "click",
        "primary_selector": {
            "code": f"getByRole('button', {{ name: '{name}' }})",
            "verification": {"checked": True, "unique": True, "visible": True},
        },
    }
    if container:
        element["ancestor_chain"] = [container]
    return element


def test_root_element_has_no_empty_context():
    assert "context" not in _snapshot_elements_for_artifact([_button("发布")], [])[0]


def test_overlay_element_keeps_only_container_identity():
    element = _snapshot_elements_for_artifact([
        _button("确认", {"role": "popover", "name": "发布菜单"})
    ], [])[0]
    assert element["context"] == {"role": "popover", "name": "发布菜单"}


def test_same_named_overlay_elements_have_distinct_keys():
    elements = _snapshot_elements_for_artifact([
        _button("确认", {"role": "dialog", "name": "发布确认"}),
        _button("确认", {"role": "dialog", "name": "删除确认"}),
    ], [])
    assert [item["key"] for item in elements] == [
        "button-确认--in--发布确认",
        "button-确认--in--删除确认",
    ]
    assert [item["context"] for item in elements] == [
        {"ordinal": 1, "role": "dialog", "name": "发布确认"},
        {"ordinal": 2, "role": "dialog", "name": "删除确认"},
    ]
