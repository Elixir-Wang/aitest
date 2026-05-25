from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.exploration import ExplorationRunCreateIn
from app.services import exploration_service
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


def seed_project_environment() -> None:
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


def admin_actor() -> dict:
    return {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


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
