from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core.db import connect
from app.services import global_knowledge_service


class GlobalKnowledgeServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_admin_uploads_markdown_global_knowledge(self):
        with isolated_global_knowledge_store() as actor:
            result = await global_knowledge_service.upload_document(
                name="通用测试规范",
                knowledge_type="test_standard",
                version="v1",
                scope="全部项目",
                source_note="团队规范",
                description="测试设计规范",
                files=[make_upload_file("standard.md", "# 测试规范\n\n- 必须有期望结果".encode("utf-8"))],
                actor=actor,
            )

            self.assertEqual(result["document"]["name"], "通用测试规范")
            self.assertEqual(result["document"]["status"], "available")
            self.assertEqual(result["document"]["version"], "v1")
            self.assertIn("必须有期望结果", result["current_version"]["markdown_content"])
            self.assertEqual(result["files"][0]["original_filename"], "standard.md")

    async def test_upload_rejects_project_id(self):
        with isolated_global_knowledge_store() as actor:
            with self.assertRaises(HTTPException) as context:
                await global_knowledge_service.upload_document(
                    name="通用测试规范",
                    knowledge_type="test_standard",
                    version="v1",
                    scope="全部项目",
                    source_note="",
                    description="",
                    project_id="project-1",
                    files=[make_upload_file("standard.md", b"# x")],
                    actor=actor,
                )

            self.assertEqual(context.exception.detail["code"], "GLOBAL_KNOWLEDGE_PROJECT_ID_FORBIDDEN")

    async def test_tester_cannot_upload(self):
        with isolated_global_knowledge_store():
            with self.assertRaises(HTTPException) as context:
                await global_knowledge_service.upload_document(
                    name="通用测试规范",
                    knowledge_type="test_standard",
                    version="v1",
                    scope="全部项目",
                    source_note="",
                    description="",
                    files=[make_upload_file("standard.md", b"# x")],
                    actor={"id": "u-tester", "role": "tester", "username": "tester"},
                )

            self.assertEqual(context.exception.detail["code"], "PERMISSION_DENIED")

    async def test_create_version_and_archive(self):
        with isolated_global_knowledge_store() as actor:
            created = await global_knowledge_service.upload_document(
                name="通用测试规范",
                knowledge_type="test_standard",
                version="v1",
                scope="全部项目",
                source_note="",
                description="",
                files=[make_upload_file("standard.md", b"# v1")],
                actor=actor,
            )

            updated = await global_knowledge_service.create_version(
                created["document"]["id"],
                version="v2",
                source_note="更新",
                change_summary="补充自动化规则",
                files=[make_upload_file("standard.md", b"# v2")],
                actor=actor,
            )

            self.assertEqual(updated["document"]["version"], "v2")
            self.assertIn("# v2", updated["current_version"]["markdown_content"])
            self.assertEqual(len(updated["versions"]), 2)

            archived = global_knowledge_service.archive_document(created["document"]["id"], actor)
            self.assertEqual(archived["document"]["status"], "archived")


def make_upload_file(filename: str, content: bytes) -> TestUploadFile:
    return TestUploadFile(filename, content)


class TestUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class isolated_global_knowledge_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        db_path = temp_path / "ai_testing.db"
        storage_root = temp_path / "projects"
        self.patches = [
            patch("app.core.db.DB_PATH", db_path),
            patch("app.core.db.DATA_DIR", temp_path),
            patch("app.core.storage.PROJECT_FILE_STORAGE_ROOT", storage_root),
        ]
        for patcher in self.patches:
            patcher.start()

        with connect() as db:
            db.executescript(
                """
                CREATE TABLE global_knowledge_documents (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  knowledge_type TEXT NOT NULL,
                  scope TEXT NOT NULL DEFAULT '全部项目',
                  source_note TEXT NOT NULL DEFAULT '',
                  description TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL,
                  current_version_id TEXT,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  archived_at TEXT,
                  UNIQUE(name, knowledge_type)
                );
                CREATE TABLE global_knowledge_versions (
                  id TEXT PRIMARY KEY,
                  document_id TEXT NOT NULL,
                  version_no TEXT NOT NULL,
                  markdown_content TEXT NOT NULL DEFAULT '',
                  markdown_path TEXT NOT NULL DEFAULT '',
                  change_summary TEXT NOT NULL DEFAULT '',
                  conversion_status TEXT NOT NULL,
                  conversion_summary TEXT NOT NULL DEFAULT '',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(document_id, version_no)
                );
                CREATE TABLE global_knowledge_files (
                  id TEXT PRIMARY KEY,
                  version_id TEXT NOT NULL,
                  original_filename TEXT NOT NULL,
                  file_path TEXT NOT NULL,
                  file_type TEXT NOT NULL DEFAULT '',
                  file_size INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE global_knowledge_usage_logs (
                  id TEXT PRIMARY KEY,
                  global_knowledge_version_id TEXT NOT NULL,
                  usage_type TEXT NOT NULL,
                  target_project_id TEXT,
                  target_object_id TEXT NOT NULL DEFAULT '',
                  summary TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE operation_logs (
                  id TEXT PRIMARY KEY,
                  log_type TEXT NOT NULL,
                  module TEXT NOT NULL,
                  action TEXT NOT NULL,
                  object_type TEXT NOT NULL,
                  object_id TEXT,
                  object_name TEXT NOT NULL DEFAULT '',
                  project_id TEXT,
                  actor_id TEXT NOT NULL DEFAULT 'system',
                  actor_name TEXT NOT NULL DEFAULT '系统',
                  source TEXT NOT NULL,
                  result TEXT NOT NULL,
                  failure_reason TEXT NOT NULL DEFAULT '',
                  summary TEXT NOT NULL DEFAULT '',
                  before_json TEXT NOT NULL DEFAULT '{}',
                  after_json TEXT NOT NULL DEFAULT '{}',
                  task_id TEXT,
                  artifact_path TEXT NOT NULL DEFAULT '[]',
                  request_id TEXT NOT NULL DEFAULT '',
                  ip_address TEXT NOT NULL DEFAULT '',
                  user_agent TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

        return {"id": "u-admin", "role": "admin", "username": "admin"}

    def __exit__(self, exc_type, exc, tb):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
