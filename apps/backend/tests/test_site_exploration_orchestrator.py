from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.services import site_exploration_orchestrator


class SiteExplorationOrchestratorTest(unittest.TestCase):
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
            screenshot_path = artifact_root / "screenshots" / "page-01.png"

            def fake_run_site_explorer(_page_url: str, target_root: Path, _forbidden_paths: str = "") -> dict:
                (target_root / "screenshots").mkdir(parents=True, exist_ok=True)
                (target_root / "snapshots").mkdir(parents=True, exist_ok=True)
                (target_root / "screenshots" / "page-01.png").write_bytes(b"fake png")
                (target_root / "snapshots" / "page-01.html").write_text("<button>新增用户</button>", encoding="utf-8")
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 2 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "pages": [
                        {
                            "title": "用户管理",
                            "url": "https://example.test/users",
                            "entry_path": "https://example.test",
                            "structure_summary": "标题：用户管理。可交互元素：button 1、input 1。",
                            "screenshot_path": "screenshots/page-01.png",
                            "snapshot_path": "snapshots/page-01.html",
                        }
                    ],
                    "elements": [
                        {
                            "name": "新增用户",
                            "type": "button",
                            "locator": "button",
                            "href": "",
                            "page_url": "https://example.test/users",
                        },
                        {
                            "name": "用户名",
                            "type": "input",
                            "locator": "input[name=\"username\"]",
                            "href": "",
                            "page_url": "https://example.test/users",
                        },
                    ],
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
                    WHERE exploration_run_id = 'explore-1' AND artifact_type = 'screenshot'
                    """
                ).fetchone()
                coverage = db.execute("SELECT * FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'").fetchone()
                page = db.execute("SELECT * FROM exploration_pages WHERE exploration_run_id = 'explore-1'").fetchone()
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
            self.assertEqual(page["title"], "用户管理")
            self.assertEqual(element_count["count"], 2)
            self.assertIsNotNone(artifact)
            self.assertTrue(artifact["file_path"].endswith("screenshots/page-01.png"))
            self.assertTrue(screenshot_path.exists())
            self.assertEqual(
                {(row["action"], row["result"], row["source"], row["task_id"]) for row in logs},
                {
                    ("start", "success", "runner", "explore-1"),
                    ("finish", "success", "runner", "explore-1"),
                },
            )

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
                document = db.execute("SELECT * FROM exploration_document_versions WHERE exploration_run_id = 'explore-1'").fetchone()
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
            self.assertTrue(document["markdown_path"].endswith("documents/exploration-v1.md"))
            self.assertTrue((Path(temp_dir) / "projects" / document["markdown_path"]).exists())
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
                (target_root / "screenshots").mkdir(parents=True, exist_ok=True)
                (target_root / "snapshots").mkdir(parents=True, exist_ok=True)
                (target_root / "screenshots" / "page-01.png").write_bytes(b"fake png")
                (target_root / "snapshots" / "page-01.html").write_text("<input placeholder='通过关键词搜索目录'>", encoding="utf-8")
                return {
                    "status": "completed",
                    "summary": "已探索 1 个页面，识别 1 个可交互元素，记录 0 个阻塞项。",
                    "log": "exploration ok",
                    "pages": [
                        {
                            "title": "百融百工",
                            "url": "https://example.test/document/manual/87",
                            "entry_path": "https://example.test/document/",
                            "structure_summary": "可交互元素：input 1。",
                            "screenshot_path": "screenshots/page-01.png",
                            "snapshot_path": "snapshots/page-01.html",
                        }
                    ],
                    "elements": [
                        {
                            "name": "通过关键词搜索目录",
                            "type": "input",
                            "locator": "input",
                            "href": "",
                            "page_url": "https://example.test/document/manual/87",
                        }
                    ],
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
                blocker = db.execute("SELECT * FROM exploration_blockers WHERE exploration_run_id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "partial")
            self.assertEqual(coverage["completion_status"], "partial")
            self.assertEqual(coverage["planned_page_count"], 0)
            self.assertEqual(coverage["explored_page_count"], 1)
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
