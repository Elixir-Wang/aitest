# apps/backend/tests/agents/page_exploration/test_schemas.py
import pytest
from pydantic import ValidationError
from app.agents.page_exploration.schemas import (
    PageArtifact, State, Element, TriggeredBy, SourceEntry
)


def test_page_artifact_minimal():
    yaml_obj = {
        "schema_version": "2.0",
        "page": {
            "id": "page-workspace",
            "title": "工作台",
            "normalized_path": "/workspace",
            "url": "https://test.example.com/workspace",
            "observed_url": "/workspace",
            "first_observed_at": "2026-07-04T10:00:00Z",
            "last_observed_at": "2026-07-04T10:15:00Z",
            "observed_by_runs": ["run-1"],
        },
        "states": [
            {
                "id": "page-workspace__root__001",
                "type": "root",
                "title": "工作台 - 列表状态",
                "triggered_by": None,
                "depth": 1,
                "last_observed_at": "2026-07-04T10:15:00Z",
                "observed_by_runs": ["run-1"],
                "dom_signature": "sha256:abc",
                "elements": [],
                "children": [],
            }
        ],
    }
    artifact = PageArtifact(**yaml_obj)
    assert artifact.schema_version == "2.0"
    assert artifact.page.id == "page-workspace"
    assert artifact.states[0].depth == 1
    assert artifact.states[0].triggered_by is None


def test_state_non_root_requires_triggered_by():
    state_dict = {
        "id": "page-x__dialog__001",
        "type": "dialog",
        "title": "弹窗",
        # triggered_by 缺失 - 即使业务逻辑允许，schema 不强制（运行时强约束）
        "depth": 2,
        "last_observed_at": "2026-07-04T10:00:00Z",
        "observed_by_runs": ["run-1"],
        "dom_signature": "sha256:def",
        "elements": [],
        "children": [],
    }
    s = State(**state_dict)
    assert s.type == "dialog"
    assert s.triggered_by is None  # schema 层允许，工具层拒


def test_state_type_must_be_in_whitelist():
    with pytest.raises(ValidationError):
        State(
            id="x__unknown__001", type="wizard",
            title="t", depth=1,
            last_observed_at="2026-07-04T10:00:00Z",
            observed_by_runs=["r"],
            dom_signature="sha256:1", elements=[], children=[],
        )


def test_triggered_by_action_whitelist():
    with pytest.raises(ValidationError):
        TriggeredBy(
            from_state="root", element_key="k",
            action="swipe", url_changed=False, observed_url="/x"
        )


def test_nested_children():
    leaf = State(
        id="page-x__form__001", type="form", title="l",
        triggered_by=TriggeredBy(
            from_state="page-x__dialog__001", element_key="k",
            action="click", url_changed=True, observed_url="/x?y=z"
        ),
        depth=3,
        last_observed_at="2026-07-04T10:00:00Z",
        observed_by_runs=["r"],
        dom_signature="sha256:leaf", elements=[], children=[],
    )
    parent = State(
        id="page-x__dialog__001", type="dialog", title="p",
        triggered_by=TriggeredBy(
            from_state="page-x__root__001", element_key="k",
            action="click", url_changed=False, observed_url="/x"
        ),
        depth=2,
        last_observed_at="2026-07-04T10:00:00Z",
        observed_by_runs=["r"],
        dom_signature="sha256:p", elements=[], children=[leaf],
    )
    assert len(parent.children) == 1
    assert parent.children[0].id == "page-x__form__001"
    assert parent.children[0].depth == 3
