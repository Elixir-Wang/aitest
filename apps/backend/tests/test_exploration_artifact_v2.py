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


def _second_page_payload() -> dict:
    page = _page_payload()
    page["page"] = {
        "id": "page-002",
        "title": "示例系统",
        "semantic_title": "用户详情页",
        "url": "https://example.test/users/1",
        "normalized_url": "https://example.test/users/1",
        "module": "用户管理",
        "status": "explored",
        "structure_summary": "用户详情页展示用户基础信息和操作入口。",
    }
    page["business_summary"] = {
        "headline": "用户详情页展示用户基础信息。",
        "primary_actions": ["编辑用户", "查看历史"],
        "filters": [],
        "observed_states": ["详情已加载"],
    }
    return page


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


def test_load_exploration_run_artifacts_does_not_mark_running_dirs_legacy(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "run.log").write_text('{"event":"run_started"}\n', encoding="utf-8")

    bundle = artifact_service.load_exploration_run_artifacts(tmp_path)

    assert bundle["artifact_schema_version"] == 0
    assert bundle["unsupported_artifact"] is False
    assert bundle["pages"] == []
    assert bundle["log_content"] == '{"event":"run_started"}\n'


def test_load_exploration_run_artifacts_recovers_running_live_snapshot(tmp_path: Path) -> None:
    page = _page_payload()
    page["steps"] = [
        {
            "id": "step-001",
            "type": "observe",
            "title": "观察页面",
            "detail": "工作台，1 个元素。",
            "status": "completed",
        }
    ]
    artifact_service.write_live_exploration_snapshot(
        tmp_path,
        run=_run_payload() | {"status": "running"},
        summary={"status": "running", "summary": "探索中。"},
        page_artifacts=[page],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[],
        log_content='{"event":"step_recorded"}\n',
    )

    bundle = artifact_service.load_exploration_run_artifacts(tmp_path)

    assert bundle["artifact_schema_version"] == 2
    assert bundle["unsupported_artifact"] is False
    assert bundle["pages"][0]["content"]["steps"][0]["detail"] == "工作台，1 个元素。"
    assert bundle["log_content"] == '{"event":"step_recorded"}\n'


def test_report_uses_graph_source_target_and_page_semantic_titles(tmp_path: Path) -> None:
    first = _page_payload()
    first["page"]["title"] = "示例系统"
    first["page"]["semantic_title"] = "用户列表页"
    first["page"]["module"] = "用户管理"
    first["business_summary"] = {
        "headline": "用户列表页展示用户列表。",
        "primary_actions": ["新建用户"],
        "filters": ["状态"],
        "observed_states": ["列表已加载"],
    }
    second = _second_page_payload()

    artifact_service.write_exploration_artifacts(
        tmp_path,
        run=_run_payload(),
        summary={"status": "completed", "summary": "探索完成。", "markdown_content": "探索完成。"},
        page_artifacts=[first, second],
        graph={
            "nodes": [
                {"id": "page-001", "title": "示例系统", "semantic_title": "用户列表页", "url": "https://example.test"},
                {"id": "page-002", "title": "示例系统", "semantic_title": "用户详情页", "url": "https://example.test/users/1"},
            ],
            "edges": [
                {
                    "id": "edge-001",
                    "source": "page-001",
                    "target": "page-002",
                    "type": "navigation",
                    "action": "click",
                    "action_target": "查看详情",
                    "result": {"status": "passed"},
                }
            ],
            "paths": [],
        },
        blockers=[],
        log_content='{"event":"run_completed"}',
    )

    report = (tmp_path / "reports" / "exploration-report.md").read_text(encoding="utf-8")

    assert "| 用户列表页 | click 查看详情 | 用户详情页 | navigation | graph.yaml |" in report
    assert "| 用户管理 | 用户列表页 | https://example.test | explored | pages/page-001-用户列表页.yaml |" in report
    assert "- | click | -" not in report
    assert "### 6.2 页面核心事实" not in report
    assert "| 页面 | 主要字段 | 主要操作 | 主要状态 | 关键说明 |" not in report


def test_report_backfills_semantic_page_titles_and_modules_for_generic_browser_titles(tmp_path: Path) -> None:
    first = _page_payload()
    first["page"].update(
        {
            "id": "page-001",
            "title": "百融百工",
            "url": "https://www.cybotstar.cn/agentStore",
            "normalized_url": "https://www.cybotstar.cn/agentStore",
            "module": "百融百工",
            "structure_summary": "标题：百融百工。正文：探索广场 结果即刻交付 全部 已订阅。",
        }
    )
    second = _page_payload()
    second["page"].update(
        {
            "id": "page-002",
            "title": "百融百工",
            "url": "https://www.cybotstar.cn/workspace/agentAnalysis?id=17990&agentId=17618",
            "normalized_url": "https://www.cybotstar.cn/workspace/agentAnalysis?id=17990&agentId=17618",
            "module": "百融百工",
            "structure_summary": "标题：百融百工。正文：数据统计 用户洞察 Token 消耗量 用户。",
        }
    )

    artifact_service.write_exploration_artifacts(
        tmp_path,
        run=_run_payload(),
        summary={"status": "completed", "summary": "探索完成。", "markdown_content": "探索完成。"},
        page_artifacts=[first, second],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[],
        log_content='{"event":"run_completed"}',
    )

    report = (tmp_path / "reports" / "exploration-report.md").read_text(encoding="utf-8")
    first_page = yaml.safe_load((tmp_path / "pages" / "page-001-探索广场.yaml").read_text(encoding="utf-8"))
    second_page = yaml.safe_load((tmp_path / "pages" / "page-002-用户洞察.yaml").read_text(encoding="utf-8"))

    assert first_page["page"]["semantic_title"] == "探索广场"
    assert first_page["page"]["module"] == "探索广场"
    assert second_page["page"]["semantic_title"] == "用户洞察"
    assert second_page["page"]["module"] == "效果评测"
    assert "| 探索广场 | 探索广场 | https://www.cybotstar.cn/agentStore | explored | pages/page-001-探索广场.yaml |" in report
    assert "| 效果评测 | 用户洞察 | https://www.cybotstar.cn/workspace/agentAnalysis?id=17990&agentId=17618 | explored | pages/page-002-用户洞察.yaml |" in report
    assert "| 百融百工 | 百融百工 |" not in report
    assert "### 6.2 页面核心事实" not in report


def test_report_fills_site_url_limits_and_avoids_structure_summary_dump(tmp_path: Path) -> None:
    run = _run_payload()
    run["site_url"] = ""
    page = _page_payload()
    page["page"]["title"] = "示例系统"
    page["page"]["semantic_title"] = "用户列表页"
    page["page"]["structure_summary"] = "很长的页面文本" * 80

    artifact_service.write_exploration_artifacts(
        tmp_path,
        run=run,
        summary={"status": "completed", "summary": "探索完成。", "markdown_content": "探索完成。"},
        page_artifacts=[page],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[],
        log_content='{"event":"run_started","url":"https://example.test/from-log"}',
    )

    run_yaml = yaml.safe_load((tmp_path / "run.yaml").read_text(encoding="utf-8"))
    report = (tmp_path / "reports" / "exploration-report.md").read_text(encoding="utf-8")

    assert run_yaml["run"]["site_url"] == "https://example.test"
    assert "- 站点 URL：https://example.test" in report
    assert "- 页面上限：50" in report
    assert "- 动作上限：1000" in report
    assert "- 超时时间：120" in report
    assert "很长的页面文本" * 20 not in report


def test_failed_page_actions_are_written_to_blockers_and_report(tmp_path: Path) -> None:
    page = _page_payload()
    page["actions"] = [
        {
            "id": "action-001",
            "type": "click",
            "element_name": "查看历史",
            "status": "failed",
            "result": {
                "error_type": "locator_timeout",
                "error_summary": "等待目标元素可执行超时。",
                "error": "locator.click: Timeout 3000ms exceeded.",
            },
        }
    ]

    artifact_service.write_exploration_artifacts(
        tmp_path,
        run=_run_payload(),
        summary={"status": "completed", "summary": "探索完成。", "markdown_content": "探索完成。"},
        page_artifacts=[page],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[],
        log_content='{"event":"action_result","status":"failed"}',
    )

    blockers = yaml.safe_load((tmp_path / "blockers.yaml").read_text(encoding="utf-8"))["blockers"]
    report = (tmp_path / "reports" / "exploration-report.md").read_text(encoding="utf-8")

    assert blockers[0]["type"] == "action_failed"
    assert blockers[0]["action"] == "查看历史"
    assert blockers[0]["impact_scope"] == "查看历史 未验证"
    assert "等待目标元素可执行超时" in report
