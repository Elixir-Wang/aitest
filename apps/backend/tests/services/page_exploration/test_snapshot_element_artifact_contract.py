"""Snapshot element artifact contract tests.

回归 bug 描述：observePage() 已经验证 primary_selector 的 unique/visible，
但 _snapshot_elements_for_artifact 调 _semantic_locator_candidates 重新生成 locator，
把 verification/code 全部丢失。导致产物 yaml 不可被外部 Playwright 自动化复用。

同时 ancestor_chain 必须透传，让外部脚本能判断元素所在 DOM 上下文（弹窗/浮层等）。

本测试是接缝修复 Step 1 的红测试：断言产出的 element 必须携带 verification/code。
"""
from app.services.page_exploration.service import (
    _snapshot_elements_for_artifact,
    _semantic_locator_candidates,
)


# ---------- _semantic_locator_candidates 直接测试 ----------

def test_semantic_locator_role_kind_carries_unique_code():
    """role-based locator 必须有 code 字段（可被 Playwright 复制粘贴）。"""
    candidates = _semantic_locator_candidates("button", "确认", "accessibility_tree")
    role_candidate = next(c for c in candidates if c["kind"] == "role")
    # 当前 bug：没有 code 字段
    assert "code" in role_candidate, f"role candidate missing 'code': {role_candidate}"
    assert role_candidate["code"] == "getByRole('button', { name: '确认' })"


def test_semantic_locator_text_kind_carries_unique_code():
    candidates = _semantic_locator_candidates("clickable", "发布", "inferred")
    text_candidate = next(c for c in candidates if c["kind"] == "text")
    assert "code" in text_candidate, f"text candidate missing 'code': {text_candidate}"
    assert text_candidate["code"] == "getByText('发布', { exact: true })"


def test_semantic_locator_role_kind_does_not_invent_verification():
    """纯生成器 _semantic_locator_candidates 不带 verification（保持纯函数）。

    verification 透传是 _attach_verification_metadata 的职责，本函数不应混入。
    """
    candidates = _semantic_locator_candidates("button", "保存", "accessibility_tree")
    role_candidate = next(c for c in candidates if c["kind"] == "role")
    assert "verification" not in role_candidate, (
        f"_semantic_locator_candidates 应保持纯函数，不应输出 verification: {role_candidate}"
    )


def test_attach_verification_metadata_emits_placeholder_for_unmatched():
    """未匹配到观察数据的 locator 也带 verification 占位（schema 完整性）。"""
    from app.services.page_exploration.service import (
        _attach_verification_metadata,
    )
    candidates = [{"kind": "role", "code": "getByRole('button', { name: 'X' })", "priority": 1}]
    observed = {"primary_selector": {"kind": "role", "code": "DIFFERENT", "verification": {"checked": True, "unique": True}}}
    attached = _attach_verification_metadata(candidates, observed)
    assert "verification" in attached[0]
    assert attached[0]["verification"]["checked"] is False


# ---------- _snapshot_elements_for_artifact 集成测试 ----------

def test_snapshot_elements_for_artifact_passes_ancestor_chain_from_observation():
    """observePage 输出的 element.ancestor_chain 必须透传到 artifact element。"""
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
                "kind": "role",
                "role": "button",
                "name": "确认",
                "code": "getByRole('button', { name: '确认' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": {
                "kind": "text",
                "text": "确认",
                "code": "getByText('确认', { exact: true })",
                "verification": {"checked": True, "unique": False, "visible": True, "match_count": 3},
            },
            "ancestor_chain": [  # ← 关键：observePage 标记了元素所在 DOM 结构
                {"role": "popover", "name": ""},
                {"role": "div", "name": ""},
            ],
        }
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    assert len(artifact_elements) == 1
    el = artifact_elements[0]
    assert el.get("ancestor_chain") == [
        {"role": "popover", "name": ""},
        {"role": "div", "name": ""},
    ], f"ancestor_chain 透传失败: {el}"


def test_snapshot_elements_for_artifact_passes_verification_from_observation():
    """observePage 验证的 primary_selector.verification 必须透传到 artifact element。"""
    observation_elements = [
        {
            "id": "el-1",
            "role": "button",
            "role_source": "accessibility_tree",
            "name": "保存",
            "text": "保存",
            "visible": True,
            "action_type": "click",
            "primary_selector": {
                "kind": "role",
                "role": "button",
                "name": "保存",
                "code": "getByRole('button', { name: '保存' })",
                "verification": {
                    "checked": True,
                    "unique": True,
                    "visible": True,
                    "match_count": 1,
                },
            },
            "fallback_selector": None,
        }
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    assert len(artifact_elements) == 1
    el = artifact_elements[0]
    locators = el.get("locators", [])
    role_loc = next((l for l in locators if l.get("kind") == "role"), None)
    assert role_loc is not None, f"role locator 缺失: {locators}"
    # 当前 bug：verification 字段被 _semantic_locator_candidates 重新生成时丢失
    assert "verification" in role_loc, f"verification 字段没透传: {role_loc}"
    assert role_loc["verification"]["unique"] is True


def test_snapshot_elements_for_artifact_preserves_unique_code():
    """artifact element locators[i].code 必须等于观察时观察到的 code。"""
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
                "kind": "role",
                "role": "button",
                "name": "提交",
                "code": "getByRole('button', { name: '提交' })",
                "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
            },
            "fallback_selector": None,
        }
    ]
    accessibility_tree: list = []
    artifact_elements = _snapshot_elements_for_artifact(observation_elements, accessibility_tree)
    role_loc = next(l for l in artifact_elements[0]["locators"] if l.get("kind") == "role")
    assert role_loc["code"] == "getByRole('button', { name: '提交' })"
