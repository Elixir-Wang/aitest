from app.services.exploration import service as exploration_service


def _run() -> dict:
    return {
        "id": "explore-1",
        "artifact_root": "project-1/exploration/explore-1",
        "goal": "",
    }


def test_load_run_artifacts_reads_elements_from_v2_states(monkeypatch) -> None:
    bundle = {
        "artifact_schema_version": 2,
        "unsupported_artifact": False,
        "unsupported_reason": "",
        "log_path": "project-1/exploration/explore-1/logs/run.log",
        "pages": [
            {
                "file_path": "project-1/exploration/explore-1/pages/page-001-首页.yaml",
                "content": {
                    "artifact_schema_version": 2,
                    "page": {
                        "id": "page-001",
                        "module": "入口页",
                        "title": "首页",
                        "url": "https://example.test",
                        "normalized_url": "https://example.test",
                        "status": "explored",
                        "structure_summary": "识别 1 个按钮。",
                    },
                    "states": [
                        {
                            "id": "default",
                            "elements": [
                                {
                                    "id": "create-user-button",
                                    "name": "新建用户",
                                    "role": "button",
                                    "primary_selector": {
                                        "kind": "role",
                                        "code": "page.getByRole('button', { name: '新建用户' })",
                                        "verification": {
                                            "checked": True,
                                            "unique": True,
                                            "visible": True,
                                            "match_count": 1,
                                        },
                                    },
                                    "fallback_selector": {
                                        "kind": "testid",
                                        "code": "page.getByTestId('create-user')",
                                        "verification": {
                                            "checked": True,
                                            "unique": True,
                                            "visible": True,
                                            "match_count": 1,
                                        },
                                    },
                                }
                            ],
                        }
                    ],
                    "steps": [],
                    "relations": {"outgoing_edges": []},
                },
            }
        ],
        "blockers": {"blockers": []},
    }
    monkeypatch.setattr(exploration_service, "_load_run_artifact_bundle", lambda run: bundle)

    pages, elements, blockers = exploration_service._load_run_artifacts(_run())

    assert pages[0]["title"] == "首页"
    assert blockers == []
    assert elements == [
        {
            "id": "page-001:default:create-user-button",
            "page_id": "page-001",
            "module_key": "入口页",
            "element_name": "新建用户",
            "element_type": "button",
            "recommended_locator": "page.getByRole('button', { name: '新建用户' })",
            "fallback_locator": "page.getByTestId('create-user')",
            "stability_note": "主 selector 已通过唯一性和可见性校验。",
            "source_ref": "https://example.test",
            "primary_selector": bundle["pages"][0]["content"]["states"][0]["elements"][0]["primary_selector"],
            "fallback_selector": bundle["pages"][0]["content"]["states"][0]["elements"][0]["fallback_selector"],
        }
    ]


def test_load_run_artifacts_returns_empty_for_unsupported_legacy_bundle(monkeypatch) -> None:
    monkeypatch.setattr(
        exploration_service,
        "_load_run_artifact_bundle",
        lambda run: {
            "artifact_schema_version": 0,
            "unsupported_artifact": True,
            "unsupported_reason": "历史产物格式不支持新版详情，请重新探索。",
            "pages": [{"content": {"page": {"title": "旧页面"}}}],
            "blockers": {"blockers": []},
            "log_path": "",
        },
    )

    assert exploration_service._load_run_artifacts(_run()) == ([], [], [])


def test_render_run_report_markdown_rebuilds_from_yaml_bundle_instead_of_stale_report_content() -> None:
    bundle = {
        "artifact_schema_version": 2,
        "unsupported_artifact": False,
        "run": {
            "run": {
                "id": "explore-1",
                "title": "百融百工探索",
                "project_name": "测试项目",
                "environment_name": "测试环境",
                "site_url": "https://www.cybotstar.cn/agentStore",
                "scope": "全站",
                "goal": "探索百融百工",
                "status": "completed",
                "summary": "探索完成。",
                "limits": {"max_pages": 50, "max_actions": 1000, "timeout_minutes": 120},
            }
        },
        "summary": {"status": "completed", "summary": "探索完成。", "goal_validation": {"status": "skipped", "summary": "未设置探索目标。"}},
        "graph": {"nodes": [], "edges": [], "paths": []},
        "blockers": {"blockers": []},
        "goal_validation": {"status": "skipped", "summary": "未设置探索目标。", "stats": {}},
        "pages": [
            {
                "file_path": "project-1/exploration/explore-1/pages/page-001-old.yaml",
                "content": {
                    "page": {
                        "id": "page-001",
                        "title": "百融百工",
                        "module": "百融百工",
                        "url": "https://www.cybotstar.cn/agentStore",
                        "status": "explored",
                        "structure_summary": "标题：百融百工。正文：探索广场 结果即刻交付 全部 已订阅。",
                    },
                    "states": [],
                    "actions": [],
                    "relations": {"outgoing_edges": []},
                    "quality": {"needs_confirmation": False},
                },
            }
        ],
        "report_content": "旧报告内容",
    }

    report = exploration_service._render_run_report_markdown(bundle)

    assert "旧报告内容" not in report
    assert "| 探索广场 | 探索广场 | https://www.cybotstar.cn/agentStore | explored | project-1/exploration/explore-1/pages/page-001-old.yaml |" in report
