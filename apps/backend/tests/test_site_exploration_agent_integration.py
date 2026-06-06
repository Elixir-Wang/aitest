from pathlib import Path

import pytest

from app.agents.site_exploration import service as site_exploration_agent_service
from app.agents.site_exploration.schemas import SiteExplorationInput, SiteExplorationOutput
from app.presentation.serializers import serialize_exploration_run
from app.services.exploration import service as exploration_service
from app.services.exploration import site_orchestrator


def test_site_orchestrator_builds_langchain_agent_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured = {}

    async def fake_plan_site_exploration(input_data):
        captured["input"] = input_data
        return SiteExplorationOutput(
            status="ready",
            runner_contract={"runner": "ts_playwright"},
            artifact_contract={"artifact_schema_version": 2},
            summary="站点探索规划完成。",
        )

    monkeypatch.setattr(site_orchestrator.site_exploration_agent_service, "plan_site_exploration", fake_plan_site_exploration)

    run = {
        "id": "explore-1",
        "project_name": "测试项目",
        "environment_name": "测试环境",
        "environment_site_url": "https://example.test",
        "scope": "/users\n/roles",
        "forbidden_paths": "/logout",
        "goal": "探索用户管理",
        "max_pages": 20,
        "max_actions": 200,
        "timeout_minutes": 30,
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "ai_letter",
        "environment_reuse_auth_state": 1,
        "environment_username": "tester",
        "environment_password_mask": "s*******3",
    }

    output = site_orchestrator._plan_run_with_agent(run, tmp_path / "explore-1")

    assert output.status == "ready"
    input_data = captured["input"]
    assert input_data.site_url == "https://example.test"
    assert input_data.scope == "/users\n/roles"
    assert input_data.forbidden_paths == "/logout"
    assert input_data.goal == "探索用户管理"
    assert input_data.login_strategy == "account_password"
    assert input_data.captcha_strategy == "ai_letter"
    assert input_data.reuse_auth_state is True
    assert input_data.has_login_credentials is True
    assert not hasattr(input_data, "project_name")
    assert not hasattr(input_data, "environment_name")
    assert not hasattr(input_data, "run_id")
    assert not hasattr(input_data, "max_pages")
    assert not hasattr(input_data, "max_actions")
    assert not hasattr(input_data, "timeout_minutes")
    assert not hasattr(input_data, "artifact_root")
    assert not hasattr(input_data, "username")
    assert not hasattr(input_data, "password")


def test_site_exploration_prompt_includes_login_summary_without_secrets() -> None:
    prompt = site_exploration_agent_service._build_site_exploration_input(
        SiteExplorationInput(
            site_url="https://example.test",
            scope="/users",
            forbidden_paths="/logout",
            goal="探索用户管理",
            login_strategy="account_password",
            captcha_strategy="ai_letter",
            reuse_auth_state=True,
            has_login_credentials=True,
        )
    )

    assert "login:" in prompt
    assert "- login_strategy: account_password" in prompt
    assert "- captcha_strategy: ai_letter" in prompt
    assert "- reuse_auth_state: true" in prompt
    assert "- has_login_credentials: true" in prompt
    assert "username:" not in prompt
    assert "password:" not in prompt
    assert "password_mask:" not in prompt


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
            "login_strategy": "reuse_state",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_password_mask": "s*******3",
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
    assert "environment_password_mask" not in result
    assert "environment_username" not in result


def test_run_snapshot_uses_environment_auth_summary_without_secrets() -> None:
    snapshot = exploration_service._run_snapshot(
        {
            "title": "首页探索",
            "status": "pending",
            "environment_id": "env-1",
            "scope": "",
            "forbidden_paths": "",
            "login_strategy": "reuse_state",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_password_mask": "s*******3",
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
    assert "environment_password_mask" not in snapshot


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
