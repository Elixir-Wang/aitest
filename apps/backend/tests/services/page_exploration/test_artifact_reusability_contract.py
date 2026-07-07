"""Step 4 端到端契约测试：observation → artifact 整链路产物可复用性。

回归场景：之前 11 个 page yaml 产物（如 page-agentRelease-agentId-19173.yaml）
的每个 element 的 locators 只有 {kind, code, priority}，没有 verification 元数据。
外部 Playwright 自动化无法判断这个 selector 今天还能不能用。

本测试模拟真实 observePage 输出 → 走 _snapshot_elements_for_artifact 整链路 →
断言产物必须满足外部脚本复用的契约。
"""
from app.services.page_exploration.service import (
    _snapshot_elements_for_artifact,
)


def test_artifact_every_element_has_verified_locators():
    """核心契约：产物每个 element 至少有一个 verified locator
    （verification.unique === True）。

    满足：外部脚本能复制 code 字段使用，不需要重新跑 snap。
    不满足：4 个 click 失败场景（多匹配 / 不可见 / 找不到）会重现。
    """
    observation_elements = [
        {
            "id": "el-1",
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
            "fallback_selector": {
                "kind": "text", "text": "确认",
                "code": "getByText('确认', { exact: true })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 3},
            },
        },
        {
            "id": "el-2",
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
            "fallback_selector": {
                "kind": "text", "text": "发布",
                "code": "getByText('发布', { exact: true })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 5},
            },
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)

    for element in artifact_elements:
        locators = element.get("locators", [])
        assert locators, f"element {element['id']} 没有 locators"
        # 每个 locator 必须有 verification 字段（即使 unmatched 也有占位）
        for loc in locators:
            assert "verification" in loc, f"{element['id']}.locators[*] 缺 verification: {loc}"
        # 至少一个 primary（priority=1）locator 必须 verified=unique=true
        primary = next((l for l in locators if l.get("priority") == 1), locators[0])
        assert primary["verification"]["unique"] is True, (
            f"{element['id']} 的 primary locator 没 verified: {primary}"
        )
        assert primary["verification"]["visible"] is True, (
            f"{element['id']} 的 primary locator 不可见: {primary}"
        )


def test_artifact_fallback_locator_carries_non_unique_verification():
    """fallback (text) locator 多匹配时，外部脚本能读到 verification.unique=false 来避开。"""
    observation_elements = [
        {
            "id": "el-1",
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
            "fallback_selector": {
                "kind": "text", "text": "确认",
                "code": "getByText('确认', { exact: true })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 3},
            },
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    el = artifact_elements[0]
    role_loc = next(l for l in el["locators"] if l["kind"] == "role")
    text_loc = next(l for l in el["locators"] if l["kind"] == "text")
    assert role_loc["verification"]["unique"] is True
    assert text_loc["verification"]["unique"] is False  # ← 关键：fallback 标 unique=false


def test_artifact_external_automation_can_reuse_code_directly():
    """端到端契约：artifact element 的 locators[i].code 必须能被 Playwright 直接调用。"""
    observation_elements = [
        {
            "id": "el-1",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "提交",
            "text": "提交",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role", "role": "button", "name": "提交",
                "code": "getByRole('button', { name: '提交' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": {
                "kind": "text", "text": "提交",
                "code": "getByText('提交', { exact: true })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    el = artifact_elements[0]

    # 模拟外部自动化脚本：复制 code → 用 page.locator 调用
    primary_code = el["locators"][0]["code"]
    fallback_code = el["locators"][1]["code"]
    # Playwright code 必须是合法的 locator 表达式
    assert primary_code.startswith("getByRole(") or primary_code.startswith("getByText(")
    assert fallback_code.startswith("getByText(")


def test_artifact_preserves_observation_ancestor_chain_in_e2e():
    """端到端契约：observation element.ancestor_chain 必须出现在 artifact element。"""
    observation_elements = [
        {
            "id": "el-1",
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
            "ancestor_chain": [{"role": "popover", "name": ""}],
        },
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    el = artifact_elements[0]
    assert el.get("ancestor_chain") == [{"role": "popover", "name": ""}], (
        f"端到端 ancestor_chain 透传失败: {el}"
    )
    assert el.get("name") == "确认"
    assert el.get("ancestor_chain") == [{"role": "popover", "name": ""}]
