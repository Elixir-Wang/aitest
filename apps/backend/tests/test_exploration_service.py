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
    def test_create_run_keeps_task_queued_until_explicit_start(self):
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

            self.assertEqual(run["status"], "queued")
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
        self.db_patch.start()
        init_db()

    def __exit__(self, exc_type, exc, tb):
        self.db_patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()

