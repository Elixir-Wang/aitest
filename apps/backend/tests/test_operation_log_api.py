from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.db import connect
from app.core.security import hash_secret
from app.main import app
from app.seed.init_db import init_db
from app.services import operation_log_service


class OperationLogApiTest(unittest.TestCase):
    def test_admin_lists_global_logs_and_tester_lists_only_project_logs(self):
        with isolated_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
                    VALUES ('u-tester', 'tester', 'tester@example.com', '测试工程师', ?, 'tester', 'enabled', '项目A', '')
                    """,
                    (hash_secret("tester"),),
                )
                db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '项目A', 'active', '')")
            operation_log_service.record_success(
                module="project",
                action="create",
                object_type="project",
                object_id="project-1",
                object_name="项目A",
                project_id="project-1",
            )

            client = TestClient(app)
            admin_token = _login(client, "admin", "admin")
            tester_token = _login(client, "tester", "tester")

            admin_response = client.get("/api/v1/operation-logs?module=project", headers=_auth(admin_token))
            self.assertEqual(admin_response.status_code, 200)
            self.assertEqual(admin_response.json()["data"]["total"], 1)

            tester_global = client.get("/api/v1/operation-logs", headers=_auth(tester_token))
            self.assertEqual(tester_global.status_code, 403)

            tester_project = client.get("/api/v1/projects/project-1/operation-logs", headers=_auth(tester_token))
            self.assertEqual(tester_project.status_code, 200)
            self.assertEqual(tester_project.json()["data"]["total"], 1)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
