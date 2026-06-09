from pathlib import Path

import pytest

from app.presentation.serializers import serialize_exploration_run
from app.services.exploration import service as exploration_service
from app.services.exploration import site_orchestrator


def test_serialize_exploration_run_uses_environment_auth_summary() -> None:
    result = serialize_exploration_run(
        {
            "id": "explore-1",
            "project_id": "project-1",
            "project_name": "测试项目",
            "environment_id": "env-1",
            "environment_name": "测试环境",
            "environment_site_url": "https://example.test",
            "title": "首页探索",
            "status": "pending",
            "scope": "",
            "forbidden_paths": "",
            "login_strategy": "account_password",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_has_password": 1,
            "goal": "",
            "notes": "",
            "max_pages": 50,
            "max_actions": 1000,
            "timeout_minutes": 120,
            "artifact_root": "",
            "result_summary": "",
            "created_at": "2026-06-06 10:00:00",
            "updated_at": "2026-06-06 10:00:00",
            "started_at": None,
            "finished_at": None,
        },
        "admin",
    )

    assert result["login_strategy"] == "account_password"
    assert result["captcha_strategy"] == "ai_letter"
    assert result["reuse_auth_state"] is True
    assert result["has_login_credentials"] is True
    assert "environment_username" not in result


def test_run_snapshot_uses_environment_auth_summary_without_secrets() -> None:
    snapshot = exploration_service._run_snapshot(
        {
            "title": "首页探索",
            "status": "pending",
            "environment_id": "env-1",
            "scope": "",
            "forbidden_paths": "",
            "login_strategy": "account_password",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_has_password": 1,
            "goal": "",
            "notes": "",
            "max_pages": 50,
            "max_actions": 1000,
            "timeout_minutes": 120,
            "result_summary": "",
        }
    )

    assert snapshot["login_strategy"] == "account_password"
    assert snapshot["captcha_strategy"] == "ai_letter"
    assert snapshot["reuse_auth_state"] is True
    assert snapshot["has_login_credentials"] is True
    assert "environment_username" not in snapshot


def test_site_orchestrator_reads_elements_from_v2_states() -> None:
    primary_selector = {
        "kind": "role",
        "code": "page.getByRole('button', { name: '新建用户' })",
        "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
    }
    fallback_selector = {
        "kind": "testid",
        "code": "page.getByTestId('create-user')",
        "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
    }
    page_artifact = {
        "page": {
            "id": "page-001",
            "module": "用户管理",
            "title": "用户列表",
            "url": "https://example.test/users",
        },
        "states": [
            {
                "id": "default",
                "elements": [
                    {
                        "id": "create-user-button",
                        "name": "新建用户",
                        "role": "button",
                        "primary_selector": primary_selector,
                        "fallback_selector": fallback_selector,
                    }
                ],
            }
        ],
        "accessibility_tree": [],
    }

    elements = site_orchestrator._elements_from_page_artifacts(
        [page_artifact],
        module_key="用户管理",
        page_url="https://example.test",
    )

    assert elements == [
        {
            "module_key": "用户管理",
            "page_id": "page-001",
            "element_name": "新建用户",
            "element_type": "button",
            "recommended_locator": "page.getByRole('button', { name: '新建用户' })",
            "fallback_locator": "page.getByTestId('create-user')",
            "stability_note": "主 selector 已通过唯一性和可见性校验。",
            "source_ref": "https://example.test/users",
            "primary_selector": primary_selector,
            "fallback_selector": fallback_selector,
        }
    ]


def test_site_orchestrator_registers_v2_report_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    created = []

    def fake_create_artifact(db, **kwargs):
        created.append(kwargs)

    monkeypatch.setattr(site_orchestrator.exploration_repo, "create_artifact", fake_create_artifact)

    site_orchestrator._persist_common_artifacts(
        object(),
        "explore-1",
        {
            "run_path": "project-1/exploration/explore-1/run.yaml",
            "summary_path": "project-1/exploration/explore-1/summary.yaml",
            "graph_path": "project-1/exploration/explore-1/graph.yaml",
            "blockers_path": "project-1/exploration/explore-1/blockers.yaml",
            "report_path": "project-1/exploration/explore-1/reports/exploration-report.md",
        },
        "project-1/exploration/explore-1/logs/run.log",
    )

    assert {
        "artifact_type": "markdown",
        "file_path": "project-1/exploration/explore-1/reports/exploration-report.md",
        "title": "探索报告",
        "summary": "站点探索 v2 产物。",
    } in [
        {
            "artifact_type": item["artifact_type"],
            "file_path": item["file_path"],
            "title": item["title"],
            "summary": item["summary"],
        }
        for item in created
    ]


def test_site_orchestrator_uses_configured_entry_with_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth_root = tmp_path / "projects"
    monkeypatch.setattr(site_orchestrator, "PROJECT_FILE_STORAGE_ROOT", auth_root)
    monkeypatch.setattr(site_orchestrator.auth_state_path.__globals__["settings"], "PROJECT_FILE_STORAGE_ROOT", auth_root)
    state_path = auth_root / "project-1" / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    run = {
        "project_id": "project-1",
        "environment_id": "env-1",
        "environment_site_url": "https://www.cybotstar.cn/agentStore",
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "manual",
        "environment_reuse_auth_state": 1,
        "forbidden_paths": "",
    }

    assert site_orchestrator._stored_auth_state_path_for_run(run) == state_path
    assert site_orchestrator._exploration_start_url(run) == "https://www.cybotstar.cn/agentStore"


def test_site_orchestrator_does_not_rewrite_login_like_configured_entry() -> None:
    run = {
        "project_id": "project-1",
        "environment_id": "env-1",
        "environment_site_url": "https://example.test/login",
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "manual",
        "environment_reuse_auth_state": 1,
    }

    assert site_orchestrator._exploration_start_url(run) == "https://example.test/login"


def test_run_site_explorer_passes_storage_state_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured = {}

    class FakeProcess:
        returncode = 0
        stdout = iter(
            [
                '{"kind":"result","payload":{"status":"completed","summary":"ok","log":"","structured_pages":[]}}',
            ]
        )

        class _Stderr:
            def read(self):
                return ""

        stderr = _Stderr()

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr(site_orchestrator, "_playwright_cli_available", lambda: True)
    monkeypatch.setattr(site_orchestrator.subprocess, "Popen", fake_popen)

    result = site_orchestrator._run_site_explorer(
        "https://example.test/",
        tmp_path / "explore-1",
        "/logout",
        "/tmp/storage-state.json",
    )

    assert result["status"] == "completed"
    assert captured["command"][-2:] == ["/logout", "/tmp/storage-state.json"]
