from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.model import ModelProviderIn
from app.schemas.user import UserCreateIn, UserUpdateIn
from app.services import auth_service, model_service, user_service


class MoreOperationLogsTest(unittest.TestCase):
    def test_auth_user_and_model_actions_write_logs(self):
        with isolated_store():
            actor = admin_actor()
            created_user = user_service.create_user(
                UserCreateIn(
                    username="tester",
                    email="tester@example.com",
                    nickname="测试",
                    password="tester-pass",
                    role="tester",
                    status="enabled",
                    project_scope="全部项目",
                    description="",
                ),
                actor,
            )
            user_service.update_user(created_user["id"], UserUpdateIn(status="disabled"), actor)

            provider = model_service.create_model_provider(
                ModelProviderIn(
                    provider="OpenAI",
                    model="gpt-test",
                    base_url="https://api.example.com",
                    api_key="sk-secret",
                    description="",
                    status="enabled",
                ),
                actor,
            )
            model_service.delete_model_provider(provider["id"], actor)

            login_result = auth_service.login("admin", "admin")
            auth_service.logout(login_result["access_token"])

            with connect() as db:
                rows = db.execute("SELECT module, action, object_type, summary, after_json FROM operation_logs").fetchall()

            keys = {(row["module"], row["action"], row["object_type"]) for row in rows}
            self.assertIn(("user", "create", "user"), keys)
            self.assertIn(("user", "update", "user"), keys)
            self.assertIn(("model", "create", "model_provider"), keys)
            self.assertIn(("model", "delete", "model_provider"), keys)
            self.assertIn(("auth", "login", "user"), keys)
            self.assertIn(("auth", "logout", "user"), keys)
            self.assertTrue(any("******" in row["after_json"] for row in rows if row["module"] == "model"))


def admin_actor() -> dict:
    return {"id": "u-admin", "role": "admin", "project_scope": "全部项目", "nickname": "平台管理员", "username": "admin"}


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
