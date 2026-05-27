from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.exploration import ExplorationRunCreateIn, ExplorationRunUpdateIn
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentUpdateIn
from app.services import environment_service, exploration_service
from unittest.mock import patch


class ExplorationServiceTest(unittest.TestCase):
    def test_create_run_keeps_task_pending_until_explicit_start(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="后台探索",
                    scope="用户管理",
                    forbidden_paths="删除",
                ),
                admin_actor(),
            )

            self.assertEqual(run["status"], "pending")
            self.assertEqual(run["result_summary"], "")

    def test_create_run_uses_environment_login_strategy(self):
        with isolated_exploration_store():
            seed_project_environment(login_strategy="account_password")

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="后台探索",
                    login_strategy="skip_login",
                ),
                admin_actor(),
            )

            self.assertEqual(run["login_strategy"], "account_password")

    def test_start_run_marks_task_as_submitted(self):
        with isolated_exploration_store():
            seed_project_environment()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            started = exploration_service.start_project_run("project-1", created["id"], admin_actor())

            self.assertEqual(started["status"], "queued")
            self.assertEqual(started["result_summary"], "探索任务已提交，等待执行。")
            self.assertIsNotNone(started["started_at"])
            self.assertIsNone(started["finished_at"])

    def test_start_full_site_run_seeds_exploration_plan_modules(self):
        with isolated_exploration_store():
            seed_project_environment()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="免登录页面测试",
                    scope="探索全部站点所有内容。从环境站点 URL 作为入口，遍历同域名下全部文档页面和页面内超链接。范围包含：文档正文链接、目录导航链接、侧边栏链接、上一篇/下一篇链接、面包屑链接。",
                ),
                admin_actor(),
            )

            exploration_service.start_project_run("project-1", created["id"], admin_actor())

            detail = exploration_service.get_project_run_detail("project-1", created["id"], admin_actor())
            modules = detail["modules"]

            self.assertGreaterEqual(len(modules), 6)
            self.assertTrue(all(module["completion_status"] == "pending" for module in modules))
            self.assertIn("文档正文链接", {module["module_name"] for module in modules})
            self.assertIn("目录导航链接", {module["module_name"] for module in modules})

    def test_running_full_site_run_detail_synthesizes_plan_when_outputs_are_missing(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '免登录页面测试', 'running',
                       '探索全部站点所有内容。范围包含：文档正文链接、目录导航链接、侧边栏链接、上一篇/下一篇链接、面包屑链接。',
                       '', 'reuse_state', 'u-admin')
                    """
                )

            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())

            modules = detail["modules"]
            self.assertGreaterEqual(len(modules), 6)
            self.assertTrue(all(module["completion_status"] == "pending" for module in modules))
            self.assertIn("侧边栏链接", {module["module_name"] for module in modules})

    def test_exploration_actions_write_operation_logs(self):
        with isolated_exploration_store():
            seed_project_environment()
            actor = admin_actor()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                actor,
            )
            exploration_service.update_project_run(
                "project-1",
                created["id"],
                ExplorationRunUpdateIn(scope="用户管理"),
                actor,
            )
            started = exploration_service.start_project_run("project-1", created["id"], actor)
            with connect() as db:
                db.execute(
                    "UPDATE exploration_runs SET status = 'blocked', result_summary = '模拟执行结束' WHERE id = ?",
                    (started["id"],),
                )
            exploration_service.delete_project_run("project-1", created["id"], actor)

            with connect() as db:
                rows = db.execute(
                    """
                    SELECT log_type, module, action, object_type, task_id
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = ?
                    """,
                    (created["id"],),
                ).fetchall()

            keys = {(row["log_type"], row["module"], row["action"], row["object_type"], row["task_id"]) for row in rows}
            expected = {
                ("task", "exploration", "create", "exploration_run", created["id"]),
                ("task", "exploration", "update", "exploration_run", created["id"]),
                ("task", "exploration", "run", "exploration_run", created["id"]),
                ("task", "exploration", "delete", "exploration_run", created["id"]),
            }
            self.assertEqual(keys, expected)

    def test_environment_actions_write_operation_logs(self):
        with isolated_exploration_store():
            seed_project()
            actor = admin_actor()
            created = environment_service.create_project_environment(
                "project-1",
                ProjectEnvironmentCreateIn(name="测试环境", site_url="https://example.test", password="secret-pass"),
                actor,
            )
            environment_service.update_project_environment(
                "project-1",
                created["id"],
                ProjectEnvironmentUpdateIn(description="回归环境"),
                actor,
            )
            environment_service.delete_project_environment("project-1", created["id"], actor)

            with connect() as db:
                rows = db.execute(
                    """
                    SELECT log_type, module, action, object_type, after_json
                    FROM operation_logs
                    WHERE module = 'environment' AND object_id = ?
                    """,
                    (created["id"],),
                ).fetchall()

            keys = {(row["log_type"], row["module"], row["action"], row["object_type"]) for row in rows}
            self.assertEqual(
                keys,
                {
                    ("config", "environment", "create", "project_environment"),
                    ("config", "environment", "update", "project_environment"),
                    ("config", "environment", "delete", "project_environment"),
                },
            )
            self.assertTrue(all("secret-pass" not in row["after_json"] for row in rows))

    def test_start_run_resets_previous_exploration_duration(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths,
                       login_strategy, result_summary, created_by, started_at, finished_at)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'completed', '用户管理', '',
                       'reuse_state', '已完成', 'u-admin', '2026-05-26 01:00:00', '2026-05-26 01:05:00')
                    """
                )

            started = exploration_service.start_project_run("project-1", "explore-1", admin_actor())

            self.assertEqual(started["status"], "queued")
            self.assertNotEqual(started["started_at"], "2026-05-26 01:00:00")
            self.assertIsNone(started["finished_at"])

    def test_stop_run_marks_running_task_as_stopping_and_logs_request(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'running', '用户管理', '', 'reuse_state', 'u-admin')
                    """
                )

            stopped = exploration_service.stop_project_run("project-1", "explore-1", admin_actor())

            self.assertEqual(stopped["status"], "stopping")
            self.assertIn("停止", stopped["result_summary"])
            with connect() as db:
                log = db.execute(
                    """
                    SELECT action, result, summary
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'cancel'
                    """
                ).fetchone()
            self.assertEqual(log["result"], "success")
            self.assertIn("停止", log["summary"])

    def test_stop_run_returns_terminal_task_without_error(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths, login_strategy, result_summary, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'blocked', '用户管理', '', 'reuse_state', '执行异常中断', 'u-admin')
                    """
                )

            stopped = exploration_service.stop_project_run("project-1", "explore-1", admin_actor())

            self.assertEqual(stopped["status"], "blocked")
            self.assertEqual(stopped["result_summary"], "执行异常中断")
            with connect() as db:
                log_count = db.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM operation_logs
                    WHERE module = 'exploration' AND object_id = 'explore-1' AND action = 'cancel'
                    """
                ).fetchone()
            self.assertEqual(log_count["count"], 0)

    def test_get_project_run_report_reads_latest_markdown_document(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            report_path = root / "projects" / "project-1" / "exploration" / "explore-1" / "documents" / "exploration-v2.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("# 探索报告\n\n- 已完成", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_document_versions
                      (id, exploration_run_id, version_no, markdown_path, change_summary, created_by)
                    VALUES
                      ('expdocv-1', 'explore-1', 2, 'project-1/exploration/explore-1/documents/exploration-v2.md', '更新报告', 'system')
                    """
                )

            report = exploration_service.get_project_run_report("project-1", "explore-1", admin_actor())

            self.assertEqual(report["version_no"], 2)
            self.assertEqual(report["change_summary"], "更新报告")
            self.assertIn("# 探索报告", report["markdown_content"])

    def test_get_project_run_log_reads_log_artifact(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            log_path = root / "projects" / "project-1" / "exploration" / "explore-1" / "logs" / "run.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("2026-05-26 10:00:00 | 开始探索\n2026-05-26 10:00:01 | 完成探索\n", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_artifacts
                      (id, exploration_run_id, artifact_type, file_path, title, summary)
                    VALUES
                      ('expart-1', 'explore-1', 'log', 'project-1/exploration/explore-1/logs/run.log', '探索执行日志', '日志')
                    """
                )

            log = exploration_service.get_project_run_log("project-1", "explore-1", admin_actor())

            self.assertEqual(log["log_path"], "project-1/exploration/explore-1/logs/run.log")
            self.assertIn("开始探索", log["log_content"])


def seed_project_environment(login_strategy: str = "reuse_state") -> None:
    seed_project()
    with connect() as db:
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, login_strategy, created_by)
            VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', ?, 'u-admin')
            """,
            (login_strategy,),
        )


def seed_project() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, created_by)
            VALUES ('project-1', '测试项目', 'active', 'u-admin')
            """
        )


def admin_actor() -> dict:
    return {"id": "u-admin", "role": "admin", "project_scope": "全部项目", "nickname": "平台管理员", "username": "admin"}


class isolated_exploration_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_patch = patch("app.core.db.DB_PATH", root / "ai_testing.db")
        self.store_path_patch = patch("app.core.storage.PROJECT_FILE_STORAGE_ROOT", root / "projects")
        self.db_patch.start()
        self.store_path_patch.start()
        init_db()
        return root

    def __exit__(self, exc_type, exc, tb):
        self.store_path_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
