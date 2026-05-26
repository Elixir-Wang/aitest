from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.services import project_service


class ProjectOperationLogsTest(unittest.TestCase):
    def test_project_create_update_delete_write_operation_logs(self):
        with isolated_store():
            actor = {"id": "u-admin", "role": "admin", "project_scope": "全部项目", "nickname": "平台管理员", "username": "admin"}
            project = project_service.create_project(ProjectCreateIn(name="日志项目", description="初始"), actor)
            project_service.update_project(project["id"], ProjectUpdateIn(description="更新后"), actor)
            project_service.delete_project(project["id"], actor)

            with connect() as db:
                rows = db.execute(
                    """
                    SELECT action, object_name, summary
                    FROM operation_logs
                    WHERE module = 'project' AND object_id = ?
                    """,
                    (project["id"],),
                ).fetchall()

            rows_by_action = {row["action"]: row for row in rows}
            self.assertEqual(set(rows_by_action), {"create", "update", "delete"})
            self.assertEqual(rows_by_action["create"]["object_name"], "日志项目")
            self.assertEqual(rows_by_action["delete"]["summary"], "删除项目：日志项目")


class isolated_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "ai_testing.db"
        self.patch = patch("app.core.db.DB_PATH", db_path)
        self.patch.start()
        init_db()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
