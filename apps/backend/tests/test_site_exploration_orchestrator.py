from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.services import exploration_service, site_exploration_orchestrator


def admin_actor() -> dict:
    return {"id": "u-admin", "role": "admin", "project_scope": "全部项目", "nickname": "平台管理员", "username": "admin"}


class SiteExplorationOrchestratorTest(unittest.TestCase):
    def test_run_exploration_marks_planned_modules_running_when_probe_starts(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '全站探索', 'queued',
                       '探索全部站点所有内容。范围包含：文档正文链接、目录导航链接',
                       '', 'reuse_state', 'u-admin')
                    """
                )

            def fake_probe(_run_id: str, _artifact_root: Path) -> dict:
                with connect() as db:
                    statuses = {
                        row["completion_status"]
                        for row in db.execute(
                            "SELECT completion_status FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'"
                        ).fetchall()
                    }
                self.assertEqual(statuses, {"running"})
                return {
                    "status": "cancelled",
                    "summary": "测试中止",
                    "log": "",
                    "log_path": "",
                }

            with patch("app.services.site_exploration_orchestrator._execute_playwright_probe", side_effect=fake_probe):
                site_exploration_orchestrator.run_exploration("explore-1")

    def test_run_exploration_records_completed_result_with_pages_and_elements(self):
        with isolated_exploration_store() as temp_dir:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )

            artifact_root = Path(temp_dir) / "projects" / "project-1" / "exploration" / "explore-1"
            def fake_run_site_explorer(_page_url: str, target_root: Path, _forbidden_paths: str = "") -> dict:
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 2 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "structured_pages": [
                        {
                            "page": {
                                "id": "page-001",
                                "title": "用户管理",
                                "url": "https://example.test/users",
                                "normalized_url": "https://example.test/users",
                                "module": "用户管理",
                                "page_type": "list",
                                "depth": 0,
                                "status": "explored",
                                "structure_summary": "标题：用户管理。可交互元素：button 1、input 1。",
                            },
                            "accessibility_tree": [
                                {"role": "button", "name": "新增用户", "locator_hint": "button", "children": []},
                                {"role": "textbox", "name": "用户名", "locator_hint": "input[name=\"username\"]", "children": []},
                            ],
                            "actions": [],
                            "forms": [],
                            "tables": [],
                            "relations": {"incoming_edges": [], "outgoing_edges": []},
                            "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                        },
                    ],
                    "graph": {"nodes": [{"id": "page-001", "url": "https://example.test/users"}], "edges": [], "paths": []},
                    "blockers": [],
                    "action_count": 1,
                    "field_count": 1,
                    "state_transition_count": 0,
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    side_effect=fake_run_site_explorer,
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                artifact = db.execute(
                    """
                    SELECT * FROM exploration_artifacts
                    WHERE exploration_run_id = 'explore-1' AND artifact_type = 'yaml' AND file_path LIKE '%summary.yaml'
                    """
                ).fetchone()
                coverage = db.execute("SELECT * FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'").fetchone()
                page_count = db.execute("SELECT COUNT(*) AS count FROM exploration_pages WHERE exploration_run_id = 'explore-1'").fetchone()
                element_count = db.execute("SELECT COUNT(*) AS count FROM exploration_elements WHERE exploration_run_id = 'explore-1'").fetchone()
                logs = db.execute(
                    """
                    SELECT action, result, source, task_id
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1'
                    """
                ).fetchall()

            self.assertEqual(run["status"], "completed")
            self.assertIn("已探索 1 个页面", run["result_summary"])
            self.assertEqual(coverage["explored_page_count"], 1)
            self.assertEqual(coverage["action_count"], 1)
            self.assertEqual(coverage["field_count"], 1)
            self.assertEqual(page_count["count"], 0)
            self.assertEqual(element_count["count"], 0)
            self.assertIsNotNone(artifact)
            self.assertTrue(artifact["file_path"].endswith("summary.yaml"))
            self.assertTrue((artifact_root / "run.yaml").exists())
            self.assertTrue((artifact_root / "summary.yaml").exists())
            self.assertTrue((artifact_root / "graph.yaml").exists())
            self.assertTrue((artifact_root / "blockers.yaml").exists())
            self.assertTrue((artifact_root / "pages" / "page-001-用户管理.yaml").exists())
            self.assertFalse((artifact_root / "screenshots").exists())
            self.assertFalse((artifact_root / "snapshots").exists())
            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())
            self.assertEqual(detail["modules"][0]["pages"][0]["title"], "用户管理")
            self.assertEqual(len(detail["modules"][0]["elements"]), 2)
            self.assertEqual(
                {(row["action"], row["result"], row["source"], row["task_id"]) for row in logs},
                {
                    ("start", "success", "runner", "explore-1"),
                    ("finish", "success", "runner", "explore-1"),
                },
            )

    def test_run_exploration_with_goal_and_unverified_button_waits_for_human(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, goal, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '', 'reuse_state',
                       '每篇文章内容的超链接和按钮，不能跳转到登陆页面', 'u-admin')
                    """
                )

            def fake_run_site_explorer(_page_url: str, _target_root: Path, _forbidden_paths: str = "") -> dict:
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 1 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "structured_pages": [
                        {
                            "page": {
                                "id": "page-001",
                                "title": "用户管理",
                                "url": "https://example.test/users",
                                "normalized_url": "https://example.test/users",
                                "module": "用户管理",
                                "status": "explored",
                                "structure_summary": "可交互元素：0。",
                            },
                            "accessibility_tree": [],
                            "actions": [
                                {"role": "button", "action_type": "click", "name": "BUTTON", "locator_hint": "button"}
                            ],
                            "relations": {"incoming_edges": [], "outgoing_edges": [{"to_url": "https://example.test/help"}]},
                        }
                    ],
                    "graph": {"nodes": [{"id": "page-001", "url": "https://example.test/users"}], "edges": [], "paths": []},
                    "blockers": [],
                    "action_count": 1,
                    "field_count": 0,
                    "state_transition_count": 0,
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch("app.services.site_exploration_orchestrator._run_site_explorer", side_effect=fake_run_site_explorer),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "waiting_human")
            self.assertIn("目标验证部分完成", run["result_summary"])
            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())
            self.assertEqual(detail["goal_validation"]["status"], "partial")
            self.assertEqual(detail["goal_validation"]["stats"]["button_unverified_count"], 1)
            self.assertEqual(detail["goal_validation"]["items"][1]["result"], "unverified")

    def test_run_exploration_with_goal_and_login_link_is_blocked(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, goal, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '', 'reuse_state',
                       '每篇文章内容的超链接和按钮，不能跳转到登陆页面', 'u-admin')
                    """
                )

            def fake_run_site_explorer(_page_url: str, _target_root: Path, _forbidden_paths: str = "") -> dict:
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 1 个链接，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "structured_pages": [
                        {
                            "page": {
                                "id": "page-001",
                                "title": "文章",
                                "url": "https://example.test/article",
                                "normalized_url": "https://example.test/article",
                                "module": "文章",
                                "status": "explored",
                                "structure_summary": "链接：1。",
                            },
                            "accessibility_tree": [],
                            "actions": [],
                            "relations": {
                                "incoming_edges": [],
                                "outgoing_edges": [{"to_url": "https://example.test/login?next=/article", "label": "继续阅读"}],
                            },
                        }
                    ],
                    "graph": {"nodes": [{"id": "page-001", "url": "https://example.test/article"}], "edges": [], "paths": []},
                    "blockers": [],
                    "action_count": 0,
                    "field_count": 0,
                    "state_transition_count": 0,
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch("app.services.site_exploration_orchestrator._run_site_explorer", side_effect=fake_run_site_explorer),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "blocked")
            self.assertIn("目标验证未通过", run["result_summary"])
            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())
            self.assertEqual(detail["goal_validation"]["status"], "failed")
            self.assertEqual(detail["goal_validation"]["stats"]["link_failed_count"], 1)

    def test_run_exploration_allows_repeated_artifact_local_page_ids_across_runs(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                for run_id, title in (("explore-1", "第一次探索"), ("explore-2", "第二次探索")):
                    db.execute(
                        """
                        INSERT INTO exploration_runs
                          (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                        VALUES
                          (?, 'project-1', 'env-1', ?, 'queued', '用户管理', '', 'reuse_state', 'u-admin')
                        """,
                        (run_id, title),
                    )

            def fake_run_site_explorer(_page_url: str, target_root: Path, _forbidden_paths: str = "") -> dict:
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 1 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "structured_pages": [
                        {
                            "page": {
                                "id": "page-001",
                                "title": "用户管理",
                                "url": "https://example.test/users",
                                "normalized_url": "https://example.test/users",
                                "module": "用户管理",
                                "page_type": "list",
                                "depth": 0,
                                "status": "explored",
                                "structure_summary": "标题：用户管理。",
                            },
                            "accessibility_tree": [
                                {"role": "button", "name": "新增用户", "locator_hint": "button", "children": []}
                            ],
                            "actions": [],
                            "forms": [],
                            "tables": [],
                            "relations": {"incoming_edges": [], "outgoing_edges": []},
                            "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                        }
                    ],
                    "graph": {"nodes": [{"id": "page-001", "url": "https://example.test/users"}], "edges": [], "paths": []},
                    "blockers": [],
                    "action_count": 1,
                    "field_count": 0,
                    "state_transition_count": 0,
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch("app.services.site_exploration_orchestrator._run_site_explorer", side_effect=fake_run_site_explorer),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")
                site_exploration_orchestrator.run_exploration("explore-2")

            with connect() as db:
                runs = db.execute(
                    "SELECT id, status, result_summary FROM exploration_runs WHERE id IN ('explore-1', 'explore-2') ORDER BY id"
                ).fetchall()
                page_count = db.execute("SELECT COUNT(*) AS count FROM exploration_pages").fetchone()

            self.assertEqual([(row["id"], row["status"]) for row in runs], [("explore-1", "completed"), ("explore-2", "completed")])
            self.assertEqual(page_count["count"], 0)
            detail = exploration_service.get_project_run_detail("project-1", "explore-2", admin_actor())
            self.assertEqual(detail["modules"][0]["pages"][0]["id"], "page-001")

    def test_run_exploration_groups_completed_result_by_page_module(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '全站探索', 'queued', '全站', '', 'reuse_state', 'u-admin')
                    """
                )

            def page(page_id: str, module: str, title: str, url: str) -> dict:
                return {
                    "page": {
                        "id": page_id,
                        "title": title,
                        "url": url,
                        "normalized_url": url,
                        "module": module,
                        "page_type": "content",
                        "depth": 1,
                        "status": "explored",
                        "structure_summary": f"标题：{title}。",
                    },
                    "accessibility_tree": [{"role": "link", "name": title, "locator_hint": "a", "children": []}],
                    "actions": [],
                    "forms": [],
                    "tables": [],
                    "relations": {"incoming_edges": [], "outgoing_edges": []},
                    "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    return_value={
                        "status": "completed",
                        "summary": "已探索 3 个页面，识别 3 个可交互元素，记录 0 个阻塞项。",
                        "log": "exploration ok",
                        "structured_pages": [
                            page("page-001", "用户管理", "用户列表", "https://example.test/users"),
                            page("page-002", "用户管理", "用户详情", "https://example.test/users/1"),
                            page("page-003", "系统设置", "权限设置", "https://example.test/settings/permissions"),
                        ],
                        "graph": {"nodes": [], "edges": [], "paths": []},
                        "blockers": [],
                        "action_count": 3,
                        "field_count": 0,
                        "state_transition_count": 0,
                    },
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                coverages = db.execute(
                    """
                    SELECT module_key, module_name, explored_page_count, completion_summary
                    FROM exploration_module_coverages
                    WHERE exploration_run_id = 'explore-1'
                    ORDER BY module_name ASC
                    """
                ).fetchall()
                page_count = db.execute("SELECT COUNT(*) AS count FROM exploration_pages WHERE exploration_run_id = 'explore-1'").fetchone()

            self.assertEqual([row["module_name"] for row in coverages], ["用户管理", "系统设置"])
            self.assertEqual({row["module_name"]: row["explored_page_count"] for row in coverages}, {"用户管理": 2, "系统设置": 1})
            self.assertIn("最近页面：用户详情", {row["module_name"]: row["completion_summary"] for row in coverages}["用户管理"])
            self.assertIn("最近页面：权限设置", {row["module_name"]: row["completion_summary"] for row in coverages}["系统设置"])
            self.assertEqual(page_count["count"], 0)
            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())
            pages = [page for module in detail["modules"] for page in module["pages"]]
            self.assertEqual({page["title"]: page["module_key"] for page in pages}, {"用户列表": "用户管理", "用户详情": "用户管理", "权限设置": "系统设置"})

    def test_run_exploration_preserves_structured_pages_graph_and_json_logs(self):
        with isolated_exploration_store() as temp_dir:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '全站探索', 'queued', '范围包含：用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )

            structured_page = {
                "page": {
                    "id": "page-001",
                    "title": "用户管理",
                    "url": "https://example.test/users",
                    "normalized_url": "https://example.test/users",
                    "module": "用户管理",
                    "page_type": "list",
                    "depth": 1,
                    "status": "explored",
                },
                "accessibility_tree": [
                    {
                        "id": "node-001",
                        "role": "button",
                        "name": "新增用户",
                        "locator_hint": "getByRole('button', { name: \"新增用户\" })",
                        "fallback_locator": "button:has-text('新增用户')",
                        "locator_confidence": "high",
                        "enabled": True,
                        "visible": True,
                        "children": [],
                    }
                ],
                "actions": [
                    {
                        "id": "action-001",
                        "role": "button",
                        "name": "新增用户",
                        "locator_hint": "getByRole('button', { name: \"新增用户\" })",
                        "action_type": "click",
                        "enabled": True,
                        "visible": True,
                    }
                ],
                "forms": [],
                "tables": [{"name": "用户列表", "columns": ["用户名", "状态"]}],
                "relations": {"incoming_edges": [], "outgoing_edges": ["edge-001"]},
                "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
            }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    return_value={
                        "status": "completed",
                        "summary": "已探索 1 个页面，识别 1 个可交互元素，记录 1 条页面关系。",
                        "log": '{"event":"run_started","run_id":"explore-1"}\n{"event":"page_captured","page_id":"page-001","artifact_path":"pages/page-001-用户管理.yaml"}\n',
                        "structured_pages": [structured_page],
                        "graph": {
                            "nodes": [{"id": "page-001", "title": "用户管理", "url": "https://example.test/users", "type": "list", "module": "用户管理"}],
                            "edges": [
                                {
                                    "id": "edge-001",
                                    "source": "page-001",
                                    "target": "page-001",
                                    "type": "open_modal",
                                    "action": "点击新增用户",
                                    "element": {"role": "button", "name": "新增用户"},
                                    "result": {"dialog_opened": True},
                                }
                            ],
                        },
                        "blockers": [],
                        "action_count": 1,
                        "field_count": 0,
                        "state_transition_count": 1,
                    },
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            artifact_root = Path(temp_dir) / "projects" / "project-1" / "exploration" / "explore-1"
            page_yaml = (artifact_root / "pages" / "page-001-用户管理.yaml").read_text(encoding="utf-8")
            graph_yaml = (artifact_root / "graph.yaml").read_text(encoding="utf-8")
            log_text = (artifact_root / "logs" / "run.log").read_text(encoding="utf-8")

            self.assertIn("children:", page_yaml)
            self.assertIn("locator_confidence: high", page_yaml)
            self.assertIn("tables:", page_yaml)
            self.assertIn("open_modal", graph_yaml)
            self.assertIn("source: page-001", graph_yaml)
            self.assertIn('"event":"page_captured"', log_text)

    def test_run_exploration_records_blocker_when_playwright_cli_is_unavailable(self):
        with isolated_exploration_store() as temp_dir:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )

            with patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=False):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                coverage = db.execute("SELECT * FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'").fetchone()
                blocker = db.execute("SELECT * FROM exploration_blockers WHERE exploration_run_id = 'explore-1'").fetchone()
                summary_artifact = db.execute(
                    """
                    SELECT * FROM exploration_artifacts
                    WHERE exploration_run_id = 'explore-1' AND artifact_type = 'yaml' AND file_path LIKE '%summary.yaml'
                    """
                ).fetchone()
                finish_log = db.execute(
                    """
                    SELECT action, result, source, failure_reason, summary
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'finish'
                    """
                ).fetchone()

            self.assertEqual(run["status"], "blocked")
            self.assertIn("Playwright CLI", run["result_summary"])
            self.assertEqual(coverage["completion_status"], "blocked")
            self.assertEqual(blocker["reason_type"], "runner_unavailable")
            self.assertTrue(summary_artifact["file_path"].endswith("summary.yaml"))
            self.assertTrue((Path(temp_dir) / "projects" / summary_artifact["file_path"]).exists())
            self.assertEqual(finish_log["result"], "failed")
            self.assertEqual(finish_log["source"], "runner")
            self.assertIn("Playwright CLI", finish_log["summary"])

    def test_run_exploration_exposes_site_explorer_log_in_blocker_and_summary(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '', 'reuse_state', 'u-admin')
                    """
                )

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    return_value={
                        "status": "blocked",
                        "summary": "Playwright 探索脚本执行失败。",
                        "log": "Playwright site exploration failed: Command timed out after 30 seconds\n",
                    },
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                blocker = db.execute("SELECT * FROM exploration_blockers WHERE exploration_run_id = 'explore-1'").fetchone()
                finish_log = db.execute(
                    """
                    SELECT failure_reason, summary
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'finish'
                    """
                ).fetchone()

            self.assertIn("Command timed out after 30 seconds", run["result_summary"])
            self.assertIn("Command timed out after 30 seconds", blocker["reason"])
            self.assertIn("Command timed out after 30 seconds", blocker["suggested_action"])
            self.assertIn("Command timed out after 30 seconds", finish_log["failure_reason"])

    def test_run_exploration_marks_running_task_blocked_after_unhandled_error(self):
        with isolated_exploration_store() as temp_dir:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '', 'reuse_state', 'u-admin')
                    """
                )

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    side_effect=RuntimeError("browser crashed"),
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                finish_log = db.execute(
                    """
                    SELECT result, failure_reason
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'finish'
                    """
                ).fetchone()

            log_path = Path(temp_dir) / "projects" / "project-1" / "exploration" / "explore-1" / "logs" / "run.log"
            self.assertEqual(run["status"], "blocked")
            self.assertIsNotNone(run["finished_at"])
            self.assertIn("browser crashed", run["result_summary"])
            self.assertTrue(log_path.exists())
            self.assertIn("browser crashed", log_path.read_text(encoding="utf-8"))
            self.assertEqual(finish_log["result"], "failed")
            self.assertIn("browser crashed", finish_log["failure_reason"])

    def test_run_exploration_does_not_overwrite_stopping_run(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'stopping', '用户管理', '', 'reuse_state', 'u-admin')
                    """
                )

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available") as available,
                patch("app.services.site_exploration_orchestrator._run_site_explorer") as explorer,
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            available.assert_not_called()
            explorer.assert_not_called()
            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "cancelled")
            self.assertIn("用户已停止", run["result_summary"])

    def test_run_exploration_marks_cancelled_when_runner_reports_cancelled(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'queued', '用户管理', '', 'reuse_state', 'u-admin')
                    """
                )

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    return_value={"status": "cancelled", "summary": "用户已停止探索。", "log": "cancelled\n"},
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                finish_log = db.execute(
                    """
                    SELECT result, summary
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'finish'
                    """
                ).fetchone()

            self.assertEqual(run["status"], "cancelled")
            self.assertEqual(finish_log["result"], "cancelled")

    def test_playwright_cli_available_uses_resolved_npx_command_path(self):
        completed = Mock(returncode=0, stdout="Version 1.60.0")

        with (
            patch("app.services.site_exploration_orchestrator.shutil.which", return_value="D:\\nodejs\\npx.CMD"),
            patch("app.services.site_exploration_orchestrator.PLAYWRIGHT_RUNNER_DIR") as runner_dir,
            patch("app.services.site_exploration_orchestrator.subprocess.run", return_value=completed) as run,
        ):
            runner_dir.exists.return_value = True

            self.assertTrue(site_exploration_orchestrator._playwright_cli_available())

        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][0], "D:\\nodejs\\npx.CMD")

    def test_run_exploration_marks_full_site_single_page_result_as_partial(self):
        with isolated_exploration_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test/document/', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '文档站探索', 'queued', '探索全部站点所有内容。', '', 'reuse_state', 'u-admin')
                    """
                )

            def fake_run_site_explorer(_page_url: str, target_root: Path, _forbidden_paths: str = "") -> dict:
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 1 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "structured_pages": [
                        {
                            "page": {
                                "id": "page-001",
                                "title": "百融百工",
                                "url": "https://example.test/document/manual/87",
                                "normalized_url": "https://example.test/document/manual/87",
                                "module": "文档",
                                "page_type": "content",
                                "depth": 0,
                                "status": "explored",
                                "structure_summary": "可交互元素：input 1。",
                            },
                            "accessibility_tree": [
                                {"role": "textbox", "name": "通过关键词搜索目录", "locator_hint": "input", "children": []}
                            ],
                            "actions": [],
                            "forms": [],
                            "tables": [],
                            "relations": {"incoming_edges": [], "outgoing_edges": []},
                            "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                        }
                    ],
                    "graph": {"nodes": [{"id": "page-001", "url": "https://example.test/document/manual/87"}], "edges": [], "paths": []},
                    "blockers": [],
                    "action_count": 0,
                    "field_count": 1,
                    "state_transition_count": 0,
                    "discovery": {
                        "visited_count": 1,
                        "discovered_link_count": 0,
                        "same_origin_link_count": 0,
                        "reason_if_stopped": "入口页未发现同源可访问链接，仅发现搜索输入框。",
                    },
                }

            with (
                patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=True),
                patch(
                    "app.services.site_exploration_orchestrator._run_site_explorer",
                    side_effect=fake_run_site_explorer,
                ),
            ):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                coverage = db.execute("SELECT * FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'").fetchone()
                blocker_count = db.execute("SELECT COUNT(*) AS count FROM exploration_blockers WHERE exploration_run_id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "partial")
            self.assertEqual(coverage["completion_status"], "partial")
            self.assertEqual(coverage["planned_page_count"], 1)
            self.assertEqual(coverage["explored_page_count"], 1)
            self.assertEqual(blocker_count["count"], 0)
            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())
            blocker = detail["modules"][0]["blockers"][0]
            self.assertEqual(blocker["reason_type"], "coverage_gap")
            self.assertIn("仅覆盖入口页", blocker["reason"])


class isolated_exploration_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_patch = patch("app.core.db.DB_PATH", root / "ai_testing.db")
        self.storage_patch = patch("app.services.site_exploration_orchestrator.PROJECT_FILE_STORAGE_ROOT", root / "projects")
        self.store_path_patch = patch("app.core.storage.PROJECT_FILE_STORAGE_ROOT", root / "projects")
        self.db_patch.start()
        self.storage_patch.start()
        self.store_path_patch.start()
        init_db()
        return root

    def __exit__(self, exc_type, exc, tb):
        self.store_path_patch.stop()
        self.storage_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
