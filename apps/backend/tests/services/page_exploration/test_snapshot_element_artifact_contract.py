"""Compact page artifact projection contract."""

from app.services.page_exploration.output_registry import _snapshot_elements_for_artifact


def _selector(code: str, *, unique: bool = True, visible: bool = True) -> dict:
    return {
        "code": code,
        "verification": {
            "checked": True,
            "unique": unique,
            "visible": visible,
            "match_count": 1 if unique else 2,
        },
    }


def test_snapshot_element_contains_only_compact_pom_fields():
    elements = _snapshot_elements_for_artifact([{
        "id": "runtime-el-1",
        "role": "button",
        "name": "创建",
        "text": "创建",
        "visible": True,
        "action_type": "click",
        "primary_selector": _selector("page.getByRole('button', { name: '创建' })"),
        "fallback_selector": _selector("getByText('创建')", unique=False),
    }], [])

    assert elements == [{
        "key": "button-创建",
        "role": "button",
        "name": "创建",
        "action": "click",
        "locators": [{"code": "getByRole('button', { name: '创建' })"}],
    }]


def test_snapshot_element_drops_unverified_observations_and_ax_only_nodes():
    elements = _snapshot_elements_for_artifact([{
        "role": "button",
        "name": "不稳定按钮",
        "primary_selector": _selector("getByText('不稳定按钮')", unique=False),
    }], [{"role": "button", "name": "仅 AX 节点"}])

    assert elements == []


def test_snapshot_element_writes_context_only_when_needed():
    observed = []
    for container in ("发布确认", "删除确认"):
        observed.append({
            "role": "button",
            "name": "确认",
            "action_type": "click",
            "ancestor_chain": [{"role": "dialog", "name": container}],
            "primary_selector": _selector(
                f"page.getByRole('dialog', {{ name: '{container}' }}).getByRole('button', {{ name: '确认' }})"
            ),
        })

    elements = _snapshot_elements_for_artifact(observed, [])

    assert [item["context"] for item in elements] == [
        {"ordinal": 1, "role": "dialog", "name": "发布确认"},
        {"ordinal": 2, "role": "dialog", "name": "删除确认"},
    ]
    assert elements[0]["key"] == "button-确认--in--发布确认"
    assert elements[1]["key"] == "button-确认--in--删除确认"
