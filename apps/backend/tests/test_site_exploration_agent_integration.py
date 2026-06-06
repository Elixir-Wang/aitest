from pathlib import Path

import pytest

from app.agents.site_exploration.schemas import SiteExplorationOutput
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
    }

    output = site_orchestrator._plan_run_with_agent(run, tmp_path / "explore-1")

    assert output.status == "ready"
    input_data = captured["input"]
    assert input_data.run_id == "explore-1"
    assert input_data.project_name == "测试项目"
    assert input_data.environment_name == "测试环境"
    assert input_data.site_url == "https://example.test"
    assert input_data.scope == "/users\n/roles"
    assert input_data.forbidden_paths == "/logout"
    assert input_data.goal == "探索用户管理"
    assert input_data.max_pages == 20
    assert input_data.max_actions == 200
    assert input_data.timeout_minutes == 30
    assert input_data.artifact_root.endswith("explore-1")


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
