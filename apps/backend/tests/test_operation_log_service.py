from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.schemas.operation_log import OperationLogCleanupRequest, OperationLogQuery, OperationLogRetentionPolicyUpdate
from app.services import operation_log_service


class OperationLogServiceTest(unittest.TestCase):
    def test_record_success_masks_sensitive_values_and_lists_logs(self):
        with isolated_operation_log_store():
            log_id = operation_log_service.record_success(
                log_type="config",
                module="model",
                action="update",
                object_type="model_provider",
                object_id="model-1",
                object_name="DeepSeek",
                actor_id="u-admin",
                actor_name="平台管理员",
                source="web",
                summary="api_key=sk-secret token=abc",
                before={"api_key": "old-secret", "nested": {"password": "old-password"}},
                after={"api_key": "new-secret", "base_url": "https://example.com"},
            )

            self.assertIsNotNone(log_id)
            result = operation_log_service.list_logs(OperationLogQuery(page=1, page_size=10), admin_actor())
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["items"][0]["summary"], "api_key=****** token=******")

            detail = operation_log_service.get_log(log_id, admin_actor())
            self.assertEqual(detail["before"]["api_key"], "******")
            self.assertEqual(detail["before"]["nested"]["password"], "******")
            self.assertEqual(detail["after"]["api_key"], "******")
            self.assertEqual(detail["after"]["base_url"], "https://example.com")

    def test_project_log_access_requires_matching_project_scope(self):
        with isolated_operation_log_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, description)
                    VALUES ('project-1', '项目A', 'active', '')
                    """
                )
            operation_log_service.record_success(
                module="project",
                action="create",
                object_type="project",
                object_id="project-1",
                object_name="项目A",
                project_id="project-1",
                actor_id="u-admin",
                actor_name="平台管理员",
                source="web",
            )

            allowed = operation_log_service.list_project_logs(
                "project-1",
                OperationLogQuery(page=1, page_size=10),
                {"id": "u-tester", "role": "tester", "project_scope": "项目A"},
            )
            self.assertEqual(allowed["total"], 1)

            with self.assertRaises(Exception) as caught:
                operation_log_service.list_project_logs(
                    "project-1",
                    OperationLogQuery(page=1, page_size=10),
                    {"id": "u-tester", "role": "tester", "project_scope": "项目B"},
                )
            self.assertEqual(caught.exception.status_code, 403)

    def test_retention_policy_and_dry_run_cleanup(self):
        with isolated_operation_log_store():
            policy = operation_log_service.update_retention_policy(
                OperationLogRetentionPolicyUpdate(retention_days=30, max_rows=1000, protect_high_risk=True),
                admin_actor(),
            )
            self.assertEqual(policy["retention_days"], 30)
            self.assertEqual(policy["max_rows"], 1000)

            operation_log_service.record_success(
                module="project",
                action="create",
                object_type="project",
                object_name="项目A",
            )
            result = operation_log_service.cleanup_logs(
                OperationLogCleanupRequest(log_type="audit", dry_run=True),
                admin_actor(),
            )
            self.assertEqual(result["matched_count"], 1)
            self.assertEqual(result["deleted_count"], 0)


def admin_actor() -> dict:
    return {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


class isolated_operation_log_store:
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
