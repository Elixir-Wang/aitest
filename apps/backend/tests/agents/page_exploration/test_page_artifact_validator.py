# apps/backend/tests/agents/page_exploration/test_page_artifact_validator.py
import pytest
from app.services.page_exploration.page_artifact_validator import (
    PageArtifactValidator, ValidationResult,
)
from app.services.page_exploration.page_artifact_writer import (
    NewStateObservation, NewElementObservation,
)
from app.agents.page_exploration.schemas import TriggeredBy


def _root_obs():
    return NewStateObservation(
        page_id="page-x", page_title="x", normalized_path="/x",
        observed_url="/x", run_id="r-1", observed_at="2026-07-04T10:00:00Z",
        state_type="root", title="root", dom_signature="sha256:t",
        triggered_by=None, parent_state_id=None, elements=[],
    )


def _child_obs(parent_id, with_trigger=True, action="click", ek="button-a"):
    tb = None
    if with_trigger:
        tb = TriggeredBy(from_state=parent_id, element_key=ek,
                         action=action, url_changed=False, observed_url="/x")
    return NewStateObservation(
        page_id="page-x", page_title="x", normalized_path="/x",
        observed_url="/x", run_id="r-1", observed_at="2026-07-04T10:00:00Z",
        state_type="dialog", title="child", dom_signature="sha256:t",
        triggered_by=tb, parent_state_id=parent_id, elements=[],
    )


def test_root_observation_passes():
    v = PageArtifactValidator()
    r = v.validate_observation(_root_obs(), existing_tree=None, parent_depth=None)
    assert r.ok


def test_from_state_must_equal_parent():
    v = PageArtifactValidator()
    root = _root_obs()
    # parent_state_id 指向 "假祖父" 而 triggered_by.from_state 也设为祖父
    bad_child = _child_obs(parent_id="page-x__form__001")  # 不是 root
    bad_child.triggered_by = TriggeredBy(
        from_state="page-x__form__001",  # 同 parent 但 parent 不是 root 这层
        element_key="button-a", action="click", url_changed=False,
        observed_url="/x"
    )
    r = v.validate_observation(bad_child, existing_tree=None,
                               parent_depth=1)
    # 没有现成树，所以 from_state 解析不到 -> 拒
    assert not r.ok
    assert any("unresolved" in i.code for i in r.issues)


def test_cross_grandparent_rejected():
    v = PageArtifactValidator()
    root = _root_obs()
    # 假设 tree 已存在 root + dialog (depth=2)；新 observation 是 form (depth 期望 3),
    # triggered_by.from_state 指向 root (depth=1) -> 跨级拒绝
    from app.agents.page_exploration.schemas import (
        PageArtifact, Page, State,
    )
    tree = PageArtifact(
        page=Page(
            id="page-x", title="x", normalized_path="/x", observed_url="/x",
            first_observed_at="2026-07-04T10:00:00Z",
            last_observed_at="2026-07-04T10:00:00Z", observed_by_runs=["r-1"],
        ),
        states=[
            State(
                id="page-x__root__001", type="root", title="root",
                triggered_by=None, depth=1,
                last_observed_at="2026-07-04T10:00:00Z",
                observed_by_runs=["r-1"], dom_signature="sha256:r",
                elements=[], children=[],
            ),
            State(
                id="page-x__dialog__001", type="dialog", title="d",
                triggered_by=TriggeredBy(
                    from_state="page-x__root__001", element_key="button-a",
                    action="click", url_changed=False, observed_url="/x"
                ),
                depth=2,
                last_observed_at="2026-07-04T10:00:00Z",
                observed_by_runs=["r-1"], dom_signature="sha256:d",
                elements=[], children=[],
            ),
        ],
    )
    # 新 form 观察: parent_state_id="page-x__dialog__001" (OK),
    # 但 triggered_by.from_state="page-x__root__001" (祖父级) -> 拒绝
    bad = _child_obs(parent_id="page-x__dialog__001")
    bad.triggered_by = TriggeredBy(
        from_state="page-x__root__001", element_key="button-a",
        action="click", url_changed=False, observed_url="/x"
    )
    r = v.validate_observation(bad, existing_tree=tree, parent_depth=2)
    assert not r.ok
    assert any(i.code == "triggered_by_from_state_not_parent" for i in r.issues)


def test_depth_exceeds_limit_rejected():
    v = PageArtifactValidator()
    # Use a non-root obs so depth is computed as parent_depth + 1 = 21 > 16
    deep_obs = _child_obs(parent_id="page-x__root__001")
    r = v.validate_observation(deep_obs, existing_tree=None, parent_depth=20)
    assert not r.ok
    assert any(i.code == "depth_exceeds_safety_limit" for i in r.issues)


def test_element_key_unresolved_rejected():
    v = PageArtifactValidator()
    bad_child = _child_obs(parent_id="page-x__root__001")
    # 指向不存在的 element_key
    bad_child.triggered_by = TriggeredBy(
        from_state="page-x__root__001", element_key="nonexistent",
        action="click", url_changed=False, observed_url="/x"
    )
    from app.agents.page_exploration.schemas import (
        PageArtifact, Page, State,
    )
    tree = PageArtifact(
        page=Page(
            id="page-x", title="x", normalized_path="/x", observed_url="/x",
            first_observed_at="2026-07-04T10:00:00Z",
            last_observed_at="2026-07-04T10:00:00Z", observed_by_runs=["r-1"],
        ),
        states=[
            State(
                id="page-x__root__001", type="root", title="root",
                triggered_by=None, depth=1,
                last_observed_at="2026-07-04T10:00:00Z",
                observed_by_runs=["r-1"], dom_signature="sha256:r",
                elements=[], children=[],
            ),
        ],
    )
    r = v.validate_observation(bad_child, existing_tree=tree, parent_depth=1)
    assert not r.ok
    assert any("element_key" in i.code for i in r.issues)


def test_compute_depth_root():
    v = PageArtifactValidator()
    assert v.compute_depth(_root_obs(), parent_depth=None) == 1


def test_compute_depth_child():
    v = PageArtifactValidator()
    child = _child_obs(parent_id="page-x__root__001")
    assert v.compute_depth(child, parent_depth=1) == 2


def test_compute_depth_grandchild():
    v = PageArtifactValidator()
    assert v.compute_depth(_child_obs(parent_id="x"), parent_depth=2) == 3
