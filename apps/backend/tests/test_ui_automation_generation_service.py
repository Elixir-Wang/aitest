from pathlib import Path

import yaml

from app.services.ui_automation import artifact_storage, context, service


def test_find_source_case_supports_manual_test_cases(monkeypatch):
    manual_case = {"id": "manual-case-1", "project_id": "project-1", "title": "手工登录用例"}
    monkeypatch.setattr(service.test_case_repo, "find_case_by_id", lambda db, case_id: None)
    monkeypatch.setattr(service.test_case_repo, "find_manual_case_by_id", lambda db, case_id: manual_case)

    source_case, is_manual = service._find_source_case(object(), "manual-case-1")

    assert source_case == manual_case
    assert is_manual is True


def test_build_case_data_creates_derived_snapshot_without_mutating_source():
    source = {
        "id": "case-1",
        "project_id": "project-1",
        "title": "登录成功",
        "preconditions": "用户已注册",
        "steps_json": '[{"id":"step-1","action":"输入用户名"}]',
        "expected_result": "进入工作台",
        "status": "approved",
        "updated_at": "2026-07-23 10:00:00",
    }

    derived = context.build_case_data(source, automation_case_id="uiauto-1")
    derived["variables"] = {"username": {"source": "environment", "key": "UI_TEST_USERNAME"}}

    assert source.get("variables") is None
    assert derived["source_test_case"]["id"] == "case-1"
    assert derived["steps"][0]["id"] == "step-1"
    assert derived["expected_results"][0]["text"] == "进入工作台"


def test_write_case_data_uses_backend_owned_path(tmp_path: Path):
    data_path = tmp_path / "data/projects/project_1/cases/login.yaml"
    payload = {"schema_version": "v1", "variables": {}}

    artifact_storage.write_yaml_atomic(data_path, payload, suite_path=tmp_path)

    assert yaml.safe_load(data_path.read_text(encoding="utf-8")) == payload


def test_write_case_data_rejects_path_outside_suite(tmp_path: Path):
    outside = tmp_path.parent / "outside.yaml"

    try:
        artifact_storage.write_yaml_atomic(outside, {}, suite_path=tmp_path)
    except ValueError as exc:
        assert "工程目录" in str(exc)
    else:
        raise AssertionError("expected directory escape rejection")


def test_build_evidence_context_reads_only_selected_exploration_files(tmp_path: Path):
    page = tmp_path / "page-login.yaml"
    page.write_text("page:\n  title: 登录页\n  elements:\n    - name: 登录按钮\n", encoding="utf-8")
    ignored = tmp_path / "ignored.log"
    ignored.write_text("secret runtime log", encoding="utf-8")

    evidence = context.build_evidence_context(
        exploration_run_id="explore-1",
        artifact_rows=[
            {"artifact_type": "page", "file_path": str(page), "title": "登录页"},
            {"artifact_type": "log", "file_path": str(ignored), "title": "运行日志"},
        ],
    )

    assert evidence["exploration_run_id"] == "explore-1"
    assert evidence["artifacts"][0]["content"]["page"]["title"] == "登录页"
    assert len(evidence["artifacts"]) == 1
