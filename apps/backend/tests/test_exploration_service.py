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

    def test_create_run_uses_default_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            self.assertEqual(run["max_pages"], 50)
            self.assertEqual(run["max_actions"], 1000)
            self.assertEqual(run["timeout_minutes"], 120)

    def test_create_run_persists_goal_and_notes_without_description(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="后台探索",
                    goal="验证链接不跳登录页",
                    notes="人工补充说明",
                ),
                admin_actor(),
            )

            self.assertEqual(run["goal"], "验证链接不跳登录页")
            self.assertEqual(run["notes"], "人工补充说明")
            self.assertNotIn("description", run)

    def test_init_db_migrates_legacy_description_without_losing_runs(self):
        with isolated_exploration_store():
            with connect() as db:
                db.executescript(
                    """
                    DROP TABLE exploration_runs;
                    CREATE TABLE exploration_runs (
                      id TEXT PRIMARY KEY,
                      project_id TEXT NOT NULL,
                      environment_id TEXT NOT NULL,
                      title TEXT NOT NULL,
                      status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'waiting_human', 'cancelled', 'partial', 'completed', 'blocked')) DEFAULT 'pending',
                      scope TEXT NOT NULL DEFAULT '',
                      forbidden_paths TEXT NOT NULL DEFAULT '',
                      login_strategy TEXT NOT NULL DEFAULT 'reuse_state',
                      description TEXT NOT NULL DEFAULT '',
                      max_pages INTEGER NOT NULL DEFAULT 50,
                      max_actions INTEGER NOT NULL DEFAULT 1000,
                      timeout_minutes INTEGER NOT NULL DEFAULT 120,
                      artifact_root TEXT NOT NULL DEFAULT '',
                      result_summary TEXT NOT NULL DEFAULT '',
                      created_by TEXT NOT NULL,
                      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      started_at TEXT,
                      finished_at TEXT,
                      FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
                      FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
                    );
                    """
                )
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
                      (id, project_id, environment_id, title, status, scope, login_strategy, description,
                       max_pages, max_actions, timeout_minutes, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '旧任务1', 'queued', '范围1', 'skip_login', '旧目标1', 10, 20, 30, 'u-admin'),
                      ('explore-2', 'project-1', 'env-1', '旧任务2', 'completed', '范围2', 'reuse_state', '旧目标2', 11, 21, 31, 'u-admin')
                    """
                )

            init_db()

            with connect() as db:
                rows = db.execute("SELECT * FROM exploration_runs ORDER BY id").fetchall()
                columns = {row["name"] for row in db.execute("PRAGMA table_info(exploration_runs)").fetchall()}

            self.assertEqual(len(rows), 2)
            self.assertIn("goal", columns)
            self.assertIn("notes", columns)
            self.assertNotIn("description", columns)
            self.assertEqual(rows[0]["status"], "pending")
            self.assertEqual(rows[0]["goal"], "旧目标1")
            self.assertEqual(rows[0]["max_pages"], 10)
            self.assertEqual(rows[1]["status"], "completed")
            self.assertEqual(rows[1]["goal"], "旧目标2")

    def test_create_run_persists_custom_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            run = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(
                    environment_id="env-1",
                    title="后台探索",
                    max_pages=25,
                    max_actions=300,
                    timeout_minutes=45,
                ),
                admin_actor(),
            )

            self.assertEqual(run["max_pages"], 25)
            self.assertEqual(run["max_actions"], 300)
            self.assertEqual(run["timeout_minutes"], 45)

    def test_update_run_persists_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            updated = exploration_service.update_project_run(
                "project-1",
                created["id"],
                ExplorationRunUpdateIn(max_pages=80, max_actions=1500, timeout_minutes=180),
                admin_actor(),
            )

            self.assertEqual(updated["max_pages"], 80)
            self.assertEqual(updated["max_actions"], 1500)
            self.assertEqual(updated["timeout_minutes"], 180)

    def test_update_run_persists_goal_and_notes(self):
        with isolated_exploration_store():
            seed_project_environment()
            created = exploration_service.create_project_run(
                "project-1",
                ExplorationRunCreateIn(environment_id="env-1", title="后台探索"),
                admin_actor(),
            )

            updated = exploration_service.update_project_run(
                "project-1",
                created["id"],
                ExplorationRunUpdateIn(goal="验证按钮不跳登录页", notes="备注"),
                admin_actor(),
            )

            self.assertEqual(updated["goal"], "验证按钮不跳登录页")
            self.assertEqual(updated["notes"], "备注")

    def test_create_run_rejects_invalid_execution_limits(self):
        with isolated_exploration_store():
            seed_project_environment()

            with self.assertRaises(Exception) as context:
                exploration_service.create_project_run(
                    "project-1",
                    ExplorationRunCreateIn(
                        environment_id="env-1",
                        title="后台探索",
                        max_pages=0,
                        max_actions=1000,
                        timeout_minutes=120,
                    ),
                    admin_actor(),
                )

            self.assertEqual(context.exception.status_code, 400)
            self.assertEqual(context.exception.detail["code"], "INVALID_EXPLORATION_LIMIT")

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
            self.assertTrue(all(module["completion_status"] == "running" for module in modules))
            self.assertIn("侧边栏链接", {module["module_name"] for module in modules})

    def test_run_detail_normalizes_explored_page_status_to_completed(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            artifact_root = root / "projects" / "project-1" / "exploration" / "explore-1"
            pages_dir = artifact_root / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
            (pages_dir / "page-001-home.yaml").write_text(
                """
page:
  id: page-001
  module: site-entry
  title: 首页
  url: https://example.test/
  normalized_url: https://example.test/
  page_type: landing
  status: explored
steps:
  - id: step-001
    type: visit
    title: 进入页面
    detail: 访问 https://example.test/
    status: completed
    source: runner
accessibility_tree: []
relations:
  outgoing_edges: []
""".lstrip(),
                encoding="utf-8",
            )
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths,
                       login_strategy, artifact_root, result_summary, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '站点探索', 'completed', '全站', '',
                       'reuse_state', 'project-1/exploration/explore-1', '已完成探索', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_module_coverages
                      (id, exploration_run_id, module_key, module_name, entry_path, planned_page_count,
                       explored_page_count, blocked_page_count, action_count, field_count,
                       state_transition_count, completion_status, completion_summary)
                    VALUES
                      ('expcov-1', 'explore-1', 'site-entry', '入口页', '全站', 1,
                       1, 0, 0, 0, 0, 'completed', '已完成探索')
                    """
                )

            detail = exploration_service.get_project_run_detail("project-1", "explore-1", admin_actor())

            page = detail["modules"][0]["pages"][0]
            self.assertEqual(page["status"], "completed")
            self.assertEqual(page["steps"][0]["id"], "step-001")
            self.assertEqual(page["steps"][0]["status"], "completed")

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

    def test_delete_run_removes_artifact_directory(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            artifact_root = root / "projects" / "project-1" / "exploration" / "explore-1"
            (artifact_root / "logs").mkdir(parents=True, exist_ok=True)
            (artifact_root / "logs" / "run.log").write_text("exploration log\n", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths,
                       login_strategy, artifact_root, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'completed', '用户管理', '',
                       'reuse_state', 'project-1/exploration/explore-1', 'u-admin')
                    """
                )

            exploration_service.delete_project_run("project-1", "explore-1", admin_actor())

            self.assertFalse(artifact_root.exists())
            with connect() as db:
                deleted = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
            self.assertIsNone(deleted)

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

    def test_update_environment_allows_unchanged_name_in_same_project(self):
        with isolated_exploration_store():
            seed_project_environment()

            updated = environment_service.update_project_environment(
                "project-1",
                "env-1",
                ProjectEnvironmentUpdateIn(name="测试环境", login_strategy="skip_login"),
                admin_actor(),
            )

            self.assertEqual(updated["name"], "测试环境")
            self.assertEqual(updated["login_strategy"], "skip_login")

    def test_update_environment_clears_credentials_when_skipping_login(self):
        with isolated_exploration_store():
            seed_project()
            actor = admin_actor()
            created = environment_service.create_project_environment(
                "project-1",
                ProjectEnvironmentCreateIn(
                    name="测试环境",
                    site_url="https://example.test",
                    username="tester",
                    password="secret-pass",
                    login_strategy="account_password",
                ),
                actor,
            )

            updated = environment_service.update_project_environment(
                "project-1",
                created["id"],
                ProjectEnvironmentUpdateIn(login_strategy="skip_login"),
                actor,
            )

            self.assertEqual(updated["login_strategy"], "skip_login")
            self.assertEqual(updated["username"], "")
            self.assertEqual(updated["password_mask"], "")

    def test_update_environment_rejects_duplicate_name_in_same_project(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, login_strategy, created_by)
                    VALUES ('env-2', 'project-1', '备用环境', 'https://backup.example.test', 'reuse_state', 'u-admin')
                    """
                )

            with self.assertRaises(Exception) as context:
                environment_service.update_project_environment(
                    "project-1",
                    "env-2",
                    ProjectEnvironmentUpdateIn(name="测试环境"),
                    admin_actor(),
                )

            self.assertEqual(context.exception.status_code, 409)
            self.assertEqual(context.exception.detail["code"], "ENVIRONMENT_CONFLICT")

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

    def test_start_run_removes_previous_artifact_directory(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            artifact_root = root / "projects" / "project-1" / "exploration" / "explore-1"
            (artifact_root / "logs").mkdir(parents=True, exist_ok=True)
            (artifact_root / "documents").mkdir(parents=True, exist_ok=True)
            (artifact_root / "logs" / "run.log").write_text("old log\n", encoding="utf-8")
            (artifact_root / "documents" / "exploration-v1.md").write_text("old report\n", encoding="utf-8")
            (artifact_root / "summary.yaml").write_text("summary: old\n", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, status, scope, forbidden_paths,
                       login_strategy, artifact_root, result_summary, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', 'completed', '用户管理', '',
                       'reuse_state', 'project-1/exploration/explore-1', '已完成', 'u-admin')
                    """
                )

            exploration_service.start_project_run("project-1", "explore-1", admin_actor())

            self.assertFalse(artifact_root.exists())

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

    def test_get_project_run_report_reads_summary_yaml(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            report_path = root / "projects" / "project-1" / "exploration" / "explore-1" / "summary.yaml"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                "run_id: explore-1\ntitle: 探索报告 v1\nstatus: completed\nsummary: 更新报告\nmarkdown_content: '# 探索报告\\n\\n- 已完成'\n",
                encoding="utf-8",
            )
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, artifact_root, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state',
                       'project-1/exploration/explore-1', 'u-admin')
                    """
                )

            report = exploration_service.get_project_run_report("project-1", "explore-1", admin_actor())

            self.assertEqual(report["version_no"], 1)
            self.assertEqual(report["change_summary"], "更新报告")
            self.assertIn("# 探索报告", report["markdown_content"])

    def test_get_project_run_report_returns_empty_content_without_summary_yaml(self):
        with isolated_exploration_store():
            seed_project_environment()
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, artifact_root, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state',
                       'project-1/exploration/explore-1', 'u-admin')
                    """
                )

            report = exploration_service.get_project_run_report("project-1", "explore-1", admin_actor())

            self.assertIsNone(report["version_no"])
            self.assertEqual(report["markdown_content"], "")
            self.assertEqual(report["change_summary"], "")

    def test_get_project_run_log_reads_yaml_artifact_log(self):
        with isolated_exploration_store() as root:
            seed_project_environment()
            log_path = root / "projects" / "project-1" / "exploration" / "explore-1" / "logs" / "run.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                '{"ts":"2026-05-30T09:57:18.357Z","event":"run_started","url":"https://example.test"}\n'
                '{"ts":"2026-05-30T09:57:21.144Z","event":"page_captured","page_id":"page-001","title":"首页","url":"https://example.test","artifact_path":"pages/page-001.yaml"}\n'
                '{"ts":"2026-05-30T09:57:22.000Z","event":"edge_created","edge_id":"edge-001","source":"page-001","target":"https://example.test/about","type":"navigation"}\n'
                "TypeError: Cannot read properties of undefined\n",
                encoding="utf-8",
            )
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, artifact_root, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state',
                       'project-1/exploration/explore-1', 'u-admin')
                    """
                )

            log = exploration_service.get_project_run_log("project-1", "explore-1", admin_actor())

            self.assertEqual(log["log_path"], "project-1/exploration/explore-1/logs/run.log")
            self.assertEqual(log["log_content"], "")
            self.assertEqual(log["total"], 4)
            self.assertEqual(log["page"], 1)
            self.assertEqual(log["page_size"], 10)
            self.assertEqual(log["items"][0]["event"], "run_started")
            self.assertEqual(log["items"][0]["timestamp"], "2026-05-30 17:57:18")
            self.assertEqual(log["items"][1]["page_title"], "首页")
            self.assertEqual(log["items"][2]["event"], "edge_created")
            self.assertEqual(log["items"][2]["page_title"], "首页")
            self.assertEqual(log["items"][2]["source_label"], "首页")
            self.assertEqual(log["items"][2]["target_label"], "https://example.test/about")
            self.assertIn("首页 -> https://example.test/about", log["items"][2]["summary"])
            self.assertEqual(log["items"][3]["level"], "error")

            raw_log = exploration_service.get_project_run_log(
                "project-1",
                "explore-1",
                admin_actor(),
                include_raw_content=True,
            )
            self.assertIn("run_started", raw_log["log_content"])

            paged = exploration_service.get_project_run_log(
                "project-1",
                "explore-1",
                admin_actor(),
                page=2,
                page_size=1,
            )
            self.assertEqual(paged["total"], 4)
            self.assertEqual(len(paged["items"]), 1)
            self.assertEqual(paged["items"][0]["event"], "page_captured")

            filtered = exploration_service.get_project_run_log(
                "project-1",
                "explore-1",
                admin_actor(),
                keyword="undefined",
                level="error",
            )
            self.assertEqual(filtered["total"], 1)
            self.assertEqual(filtered["items"][0]["event"], "raw")

            page_filtered = exploration_service.get_project_run_log(
                "project-1",
                "explore-1",
                admin_actor(),
                type_filter="page",
                page_ref="首页",
            )
            self.assertEqual(page_filtered["total"], 1)
            self.assertEqual(page_filtered["items"][0]["event"], "page_captured")


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
