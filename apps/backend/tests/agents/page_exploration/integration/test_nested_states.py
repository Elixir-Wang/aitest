# apps/backend/tests/agents/page_exploration/integration/test_nested_states.py
import yaml
from pathlib import Path

from app.services.page_exploration.page_artifact_writer import PageArtifactWriter
from app.services.page_exploration.page_artifact_validator import PageArtifactValidator
from app.agents.page_exploration.tools.artifact_tools import merge_page_artifact


def _root_observed(run_id="run-1"):
    """Root observation for test_case3.

    dom_signature 是由 elements 内容决定的，不可用占位符。
    用 sha256:root 表示"同一 DOM 结构的稳定签名"，每次调用
    elements 相同则签名相同（_compute_state_sig 忽略 run_id）。
    """
    return {
        "page_id": "page-workspace", "page_title": "工作台",
        "normalized_path": "/workspace",
        "observed_url": "/workspace", "run_id": run_id,
        "observed_at": "2026-07-04T10:00:00Z",
        "state_type": "root", "title": "工作台 - 列表状态",
        # 稳定签名：此 elements 内容对应的 signature 由 PageArtifactWriter._compute_state_sig 决定
        "dom_signature": "sha256:root",
        "triggered_by": None,
        "parent_state_id": None,
        "elements": [
            {
                "key": "button-create-agent",
                "source": {"role": "button", "name": "创建"},
                "inferred": False,
            }
        ],
    }


def _dialog_observed(parent_id, with_parent=True):
    return {
        "page_id": "page-workspace", "page_title": "工作台",
        "normalized_path": "/workspace",
        "observed_url": "/workspace", "run_id": "run-1",
        "observed_at": "2026-07-04T10:05:00Z",
        "state_type": "dialog", "title": "选择创建类型",
        "dom_signature": "sha256:dialog",
        "triggered_by": {
            "from_state": parent_id, "element_key": "button-create-agent",
            "action": "click", "url_changed": False, "observed_url": "/workspace"
        },
        "parent_state_id": parent_id if with_parent else None,
        "elements": [
            {
                "key": "button-create-agent",
                "source": {"role": "button", "name": "创建"},
                "inferred": False,
            },
            {
                "key": "button-create-autonomous",
                "source": {"role": "button", "name": "自主规划"},
                "inferred": False,
            },
            {
                "key": "button-create-template",
                "source": {"role": "button", "name": "从模板创建"},
                "inferred": False,
            },
        ],
    }


# ---- Case 1: 单页单弹窗 ----
def test_case1_single_dialog(tmp_path: Path):
    result = merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[_root_observed(), _dialog_observed(
            parent_id="page-workspace__root__001"
        )],
    )
    assert result["skipped_due_to_lock"] is False
    page_yaml = tmp_path / "proj-x" / "page_exploration" / "pages" / "page-workspace.yaml"
    data = yaml.safe_load(page_yaml.read_text(encoding="utf-8"))
    # states list has 1 root; dialog is its child (tree model)
    assert len(data["states"]) == 1
    root = data["states"][0]
    children = root["children"]
    assert len(children) == 1
    dialog = children[0]
    assert root["type"] == "root"
    assert dialog["type"] == "dialog"
    assert dialog["triggered_by"]["from_state"] == "page-workspace__root__001"
    assert dialog["triggered_by"]["element_key"] == "button-create-agent"
    assert dialog["triggered_by"]["url_changed"] is False


# ---- Case 2: 嵌套双层 ----
def test_case2_double_nested(tmp_path: Path):
    # 先初始化 root + dialog 层
    merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[_root_observed(), _dialog_observed(
            parent_id="page-workspace__root__001"
        )],
    )
    # 现在再 merge 一个 form 层（双层嵌套触发）
    form_obs = {
        "page_id": "page-workspace", "page_title": "工作台",
        "normalized_path": "/workspace",
        "observed_url": "/workspace?dialog=create&type=auto",
        "run_id": "run-1",
        "observed_at": "2026-07-04T10:10:00Z",
        "state_type": "form", "title": "新建智能体表单",
        "dom_signature": "sha256:form",
        "triggered_by": {
            "from_state": "page-workspace__dialog__001",
            "element_key": "button-create-autonomous",
            "action": "click", "url_changed": True,
            "observed_url": "/workspace?dialog=create&type=auto"
        },
        "parent_state_id": "page-workspace__dialog__001",
        "elements": [
            {"key": "input-name", "source": {"role": "textbox", "label": "name"},
             "inferred": False},
        ],
    }
    merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[form_obs],
    )
    page_yaml = tmp_path / "proj-x" / "page_exploration" / "pages" / "page-workspace.yaml"
    data = yaml.safe_load(page_yaml.read_text(encoding="utf-8"))
    state_root = data["states"][0]
    assert state_root["depth"] == 1
    dialog = state_root["children"][0]
    assert dialog["depth"] == 2
    form = dialog["children"][0]
    assert form["type"] == "form"
    assert form["depth"] == 3
    assert form["triggered_by"]["from_state"] == "page-workspace__dialog__001"
    assert form["triggered_by"]["url_changed"] is True
    assert "dialog=create&type=auto" in form["triggered_by"]["observed_url"]


# ---- Case 3: 跨 run 合并幂等（dom_signature 驱动） ----
def test_case3_merge_idempotent(tmp_path: Path):
    # run 1: 1 root + 1 dialog
    merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[_root_observed(), _dialog_observed(
            parent_id="page-workspace__root__001"
        )],
    )
    page_yaml = tmp_path / "proj-x" / "page_exploration" / "pages" / "page-workspace.yaml"
    data = yaml.safe_load(page_yaml.read_text(encoding="utf-8"))
    # 从写入后的 state 读取真实 dom_signature（由 elements 内容决定）
    root_sig = data["states"][0]["dom_signature"]

    # run 2: 同一 page_id，root 用相同 sig → 应合并到同一 root state
    root_run2 = _root_observed(run_id="run-2")
    root_run2["dom_signature"] = root_sig
    new_dialog = _dialog_observed(parent_id="page-workspace__root__001")
    new_dialog["elements"].append({
        "key": "button-create-team",
        "source": {"role": "button", "name": "团队创建"},
        "inferred": False,
    })
    new_dialog["triggered_by"] = {
        "from_state": "page-workspace__root__001",
        "element_key": "button-create-agent",  # same as run-1 dialog
        "action": "click", "url_changed": False, "observed_url": "/workspace"
    }
    result = merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-2",
        base_dir=tmp_path,
        observed_states=[root_run2, new_dialog],
    )
    # root + dialog 都应更新而非新增
    assert result["added_state_ids"] == [], f"期望无新增 state，实际: {result['added_state_ids']}"
    assert result["updated_state_ids"] == ["page-workspace__root__001", "page-workspace__dialog__001"]

    data = yaml.safe_load(page_yaml.read_text(encoding="utf-8"))
    # total states = 2 (root + dialog)
    all_states = []
    def walk(s):
        all_states.append(s)
        for c in s.get("children", []):
            walk(c)
    walk(data["states"][0])
    assert len(all_states) == 2
    # 新元素被合并到现有 dialog
    dialog = data["states"][0]["children"][0]
    dialog_element_keys = {e["key"] for e in dialog["elements"]}
    assert "button-create-team" in dialog_element_keys


def test_case3b_root_sig_mismatch_creates_new_state(tmp_path: Path):
    """root state dom_signature 不同时应视为不同 state，追加新的 root。"""
    merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[_root_observed()],
    )
    # run 2: root sig 不同 → 视为新 state（模拟页面内容变化）
    root_run2 = _root_observed(run_id="run-2")
    root_run2["dom_signature"] = "sha256:different"  # 故意设不同
    result = merge_page_artifact(
        page_id="page-workspace", project_id="proj-x", run_id="run-2",
        base_dir=tmp_path,
        observed_states=[root_run2],
    )
    # 原有 root 保留，新增第二个 root；sig 不匹配则旧 root 不在 updated_state_ids
    assert result["added_state_ids"] == ["page-workspace__root__002"]
    assert result["updated_state_ids"] == []


# ---- Case 4: 跨祖父级拒绝 ----
def test_case4_grandparent_trigger_rejected(tmp_path: Path):
    # 直接用 validator 验证跨祖父级 triggered_by 违规
    from app.services.page_exploration.page_artifact_writer import (
        PageArtifactWriter, NewStateObservation,
    )
    from app.services.page_exploration.page_artifact_validator import PageArtifactValidator
    from app.agents.page_exploration.schemas import TriggeredBy

    # 准备 root + dialog 树（写入 tmp_path）
    writer = PageArtifactWriter(tmp_path)
    root_obs = NewStateObservation(
        page_id="page-workspace", page_title="工作台",
        normalized_path="/workspace", observed_url="/workspace",
        run_id="run-1", observed_at="2026-07-04T10:00:00Z",
        state_type="root", title="root",
        dom_signature="sha256:root", triggered_by=None,
        parent_state_id=None, elements=[],
    )
    dialog_obs = NewStateObservation(
        page_id="page-workspace", page_title="工作台",
        normalized_path="/workspace", observed_url="/workspace",
        run_id="run-1", observed_at="2026-07-04T10:05:00Z",
        state_type="dialog", title="dialog",
        dom_signature="sha256:dialog",
        triggered_by=TriggeredBy(
            from_state="page-workspace__root__001",
            element_key="button-create-agent",
            action="click", url_changed=False, observed_url="/workspace",
        ),
        parent_state_id="page-workspace__root__001",
        elements=[],
    )
    writer.merge_states([root_obs, dialog_obs])

    # 读取回 PageArtifact
    from app.agents.page_exploration.schemas import PageArtifact
    import yaml
    path = tmp_path / "pages" / "page-workspace.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    tree = PageArtifact(**data)

    # 构造祖父级违规: from_state=root, parent_state_id=dialog
    bad_obs = NewStateObservation(
        page_id="page-workspace", page_title="工作台",
        normalized_path="/workspace", observed_url="/workspace?type=auto",
        run_id="run-1", observed_at="2026-07-04T10:10:00Z",
        state_type="form", title="bad-form",
        dom_signature="sha256:bad",
        triggered_by=TriggeredBy(
            from_state="page-workspace__root__001",  # 祖父
            element_key="button-create-agent",
            action="click", url_changed=True, observed_url="/workspace?type=auto",
        ),
        parent_state_id="page-workspace__dialog__001",  # 直接父
        elements=[],
    )
    validator = PageArtifactValidator()
    r = validator.validate_observation(bad_obs, existing_tree=tree, parent_depth=2)
    assert not r.ok
    assert any(i.code == "triggered_by_from_state_not_parent" for i in r.issues)


# ---- Case 5: 深度超 16 拒绝 ----
def test_case5_depth_exceeds_16_rejected(tmp_path: Path):
    # 直接构造一个声称 parent_depth=17 的 observation（绕过 schema 不管 - merge_states 只校验）
    # 通过直接调 writer + validator 来验证
    from app.services.page_exploration.page_artifact_writer import (
        PageArtifactWriter, NewStateObservation,
    )
    from app.agents.page_exploration.schemas import TriggeredBy
    # 用 legacy tool 难触发此 case, 退而用 validator 直接测
    from app.services.page_exploration.page_artifact_validator import PageArtifactValidator

    obs = NewStateObservation(
        page_id="page-x", page_title="x", normalized_path="/x",
        observed_url="/x", run_id="r", observed_at="2026-07-04T10:00:00Z",
        state_type="dialog", title="too-deep",
        dom_signature="sha256:x", triggered_by=None,
        parent_state_id="page-x__root__001",
        elements=[],
    )
    validator = PageArtifactValidator()
    r = validator.validate_observation(obs, existing_tree=None, parent_depth=17)
    assert not r.ok
    assert any(i.code == "depth_exceeds_safety_limit" for i in r.issues)
