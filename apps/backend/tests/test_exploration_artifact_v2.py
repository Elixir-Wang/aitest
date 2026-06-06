from pathlib import Path

import yaml

from app.services.exploration import artifact_service


def _run_payload() -> dict:
    return {
        "id": "explore-1",
        "project_id": "project-1",
        "project_name": "测试项目",
        "environment_id": "env-1",
        "environment_name": "测试环境",
        "title": "首页探索",
        "site_url": "https://example.test",
        "scope": "全站",
        "goal": "探索首页",
        "forbidden_paths": "",
        "login_strategy": "skip_login",
        "captcha_strategy": "",
        "default_role": "",
        "started_at": "2026-06-06T10:00:00+08:00",
        "max_pages": 50,
        "max_actions": 1000,
        "timeout_minutes": 120,
    }


def _page_payload() -> dict:
    return {
        "artifact_schema_version": 2,
        "page": {
            "id": "page-001",
            "title": "首页",
            "url": "https://example.test",
            "normalized_url": "https://example.test",
            "module": "入口页",
            "status": "explored",
            "structure_summary": "识别 1 个按钮。",
        },
        "states": [
            {
                "id": "default",
                "type": "page",
                "elements": [
                    {
                        "id": "create-user-button",
                        "name": "新建用户",
                        "role": "button",
                        "action": "click",
                        "primary_selector": {
                            "kind": "role",
                            "code": "page.getByRole('button', { name: '新建用户' })",
                            "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                        },
                        "fallback_selector": {
                            "kind": "testid",
                            "code": "page.getByTestId('create-user')",
                            "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                        },
                    }
                ],
            }
        ],
        "accessibility_tree": [],
        "actions": [],
        "forms": [],
        "tables": [],
        "relations": {"incoming_edges": [], "outgoing_edges": []},
        "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
    }


def test_write_exploration_artifacts_uses_v2_schema_and_report_path(tmp_path: Path) -> None:
    paths = artifact_service.write_exploration_artifacts(
        tmp_path,
        run=_run_payload(),
        summary={"status": "completed", "summary": "探索完成。", "markdown_content": "探索完成。"},
        page_artifacts=[_page_payload()],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[],
        log_content='{"event":"run_completed"}',
    )

    assert (tmp_path / "reports" / "exploration-report.md").exists()
    assert not (tmp_path / "documents" / "exploration-v1.md").exists()
    assert paths["report_path"].replace("\\", "/").endswith("reports/exploration-report.md")

    run_yaml = yaml.safe_load((tmp_path / "run.yaml").read_text(encoding="utf-8"))
    summary_yaml = yaml.safe_load((tmp_path / "summary.yaml").read_text(encoding="utf-8"))
    page_yaml = yaml.safe_load((tmp_path / "pages" / "page-001-首页.yaml").read_text(encoding="utf-8"))

    assert run_yaml["artifact_schema_version"] == 2
    assert summary_yaml["artifact_schema_version"] == 2
    assert page_yaml["artifact_schema_version"] == 2

    bundle = artifact_service.load_exploration_run_artifacts(tmp_path)
    assert bundle["artifact_schema_version"] == 2
    assert bundle["unsupported_artifact"] is False
    assert bundle["report_content"].startswith("# 首页探索")


def test_load_exploration_run_artifacts_marks_legacy_artifacts_unsupported(tmp_path: Path) -> None:
    (tmp_path / "run.yaml").write_text(yaml.safe_dump({"run": {"id": "explore-legacy"}}), encoding="utf-8")
    (tmp_path / "summary.yaml").write_text(yaml.safe_dump({"title": "探索报告 v1"}), encoding="utf-8")

    bundle = artifact_service.load_exploration_run_artifacts(tmp_path)

    assert bundle["artifact_schema_version"] == 0
    assert bundle["unsupported_artifact"] is True
    assert "历史产物格式不支持新版详情，请重新探索" in bundle["unsupported_reason"]
    assert bundle["pages"] == []
