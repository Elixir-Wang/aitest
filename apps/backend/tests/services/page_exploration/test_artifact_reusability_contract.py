"""Permanent page artifacts contain executable POM data and no run noise."""

from app.services.page_exploration.output_registry import _snapshot_elements_for_artifact


def test_verified_locator_is_normalized_and_deduplicated():
    verified = {
        "checked": True,
        "unique": True,
        "visible": True,
        "match_count": 1,
    }
    elements = _snapshot_elements_for_artifact([{
        "role": "textbox",
        "name": "智能体名称",
        "primary_selector": {
            "code": "page.getByLabel('智能体名称')",
            "verification": verified,
        },
        "fallback_selector": {
            "code": "getByLabel('智能体名称')",
            "verification": verified,
        },
    }], [])

    assert elements[0]["locators"] == [{"code": "getByLabel('智能体名称')"}]


def test_artifact_element_forbids_runtime_and_duplicated_fields():
    element = _snapshot_elements_for_artifact([{
        "id": "obs-1.el-1",
        "role": "button",
        "name": "保存",
        "text": "保存",
        "visible": True,
        "primary_selector": {
            "code": "getByRole('button', { name: '保存' })",
            "verification": {"checked": True, "unique": True, "visible": True},
        },
    }], [])[0]

    forbidden = {
        "id", "element_key", "text", "action_type", "visible",
        "identity", "runtime", "ancestor_chain",
    }
    assert forbidden.isdisjoint(element)
    assert all(set(locator) == {"code"} for locator in element["locators"])
