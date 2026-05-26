from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.agent import AgentModelAssignmentIn, AgentRunIn
from app.services import agent_service


class AgentOperationLogsTest(unittest.TestCase):
    def test_update_model_assignment_writes_operation_log(self):
        with isolated_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'DeepSeek', 'deepseek-chat', 'https://api.deepseek.com', 'sk-secret', '', 'enabled', 'u-admin')
                    """
                )

            agent_service.update_model_assignment("requirement_merge", AgentModelAssignmentIn(model_provider_id="mp-1"), admin_actor())

            with connect() as db:
                row = db.execute(
                    """
                    SELECT log_type, module, action, object_type, object_id, after_json
                    FROM operation_logs
                    WHERE module = 'agent' AND action = 'assign_model'
                    """
                ).fetchone()

            self.assertEqual(row["log_type"], "config")
            self.assertEqual(row["object_type"], "agent_model_assignment")
            self.assertEqual(row["object_id"], "requirement_merge")
            self.assertNotIn("sk-secret", row["after_json"])

    def test_execute_agent_writes_agent_run_log(self):
        class Result:
            run_id = "agentrun-1"
            agent_id = "requirement_merge"
            output = {"ok": True}
            model = "gpt-test"
            model_provider_id = "mp-1"
            provider = "OpenAI"
            base_url = "https://api.example.com"
            skill_ids = ["requirement_markdown_merge"]
            tool_names = []
            raw_response_count = 1
            item_count = 2
            usage = {"input_tokens": 10}

        with isolated_store():
            with patch("app.services.agent_service.run_agent", return_value=Result()):
                result = asyncio.run(agent_service.execute_agent("requirement_merge", AgentRunIn(prompt="合并需求"), admin_actor()))

            with connect() as db:
                row = db.execute(
                    """
                    SELECT log_type, module, action, object_type, object_id, task_id
                    FROM operation_logs
                    WHERE module = 'agent' AND action = 'run'
                    """
                ).fetchone()

            self.assertEqual(result["run_id"], "agentrun-1")
            self.assertEqual(row["log_type"], "agent")
            self.assertEqual(row["object_type"], "agent")
            self.assertEqual(row["object_id"], "requirement_merge")
            self.assertEqual(row["task_id"], "agentrun-1")


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
