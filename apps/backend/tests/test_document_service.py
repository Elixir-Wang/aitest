from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.repositories import document_repo
from app.schemas.document import SourceDocumentUpdateIn
from app.services import document_service
from fastapi import HTTPException


class DocumentServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_conflict_table_exists_in_isolated_store(self):
        with isolated_document_store():
            with connect() as db:
                rows = db.execute("PRAGMA table_info(source_document_merge_conflicts)").fetchall()

        self.assertIn("resolution", {row["name"] for row in rows})

    async def test_upload_new_requirement_creates_one_document_with_multiple_pending_files(self):
        with isolated_document_store() as actor:
            files = [
                make_upload_file("登录需求.md", "# 登录需求".encode("utf-8")),
                make_upload_file("补充说明.txt", "补充说明".encode("utf-8")),
            ]

            result = await document_service.upload_documents(
                "project-1",
                files,
                actor,
                mode="new",
                document_name="统一登录需求",
            )

            self.assertEqual(result["document"]["name"], "统一登录需求")
            self.assertIsNone(result["document"]["current_version_id"])
            self.assertEqual(result["document"]["file_count"], 2)
            self.assertEqual(result["document"]["status"], "pending_merge")
            self.assertEqual(len(result["files"]), 2)
            self.assertEqual({item["mapping_status"] for item in result["files"]}, {"pending_merge"})
            self.assertEqual({item["conversion_status"] for item in result["files"]}, {"success"})
            self.assertEqual(document_service.get_document_versions(result["document"]["id"]), [])

    async def test_upload_append_requirement_adds_files_without_changing_current_version(self):
        with isolated_document_store() as actor:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '旧需求', 'PRD', 'docver-1', 'versioned', 'u-admin')
                    """
                )
                document_repo.create_version(
                    db,
                    version_id="docver-1",
                    document_id="doc-1",
                    version_no=1,
                    file_path="markdown/v1.md",
                    source_action="merge",
                    change_summary="首次归并",
                    diff_summary="首次归并。",
                    created_by="u-admin",
                )

            result = await document_service.upload_documents(
                "project-1",
                [make_upload_file("追加.md", "# 追加".encode("utf-8"))],
                actor,
                mode="append",
                existing_document_id="doc-1",
            )

            self.assertEqual(result["document"]["id"], "doc-1")
            self.assertEqual(result["document"]["current_version_id"], "docver-1")
            self.assertEqual(result["document"]["file_count"], 1)
            self.assertEqual(result["document"]["status"], "pending_merge")
            self.assertEqual(result["files"][0]["version_id"], None)
            self.assertEqual(result["files"][0]["mapping_status"], "pending_merge")

    async def test_upload_new_requirement_rejects_duplicate_name_in_project(self):
        with isolated_document_store() as actor:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '重复需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )

            with self.assertRaises(HTTPException) as caught:
                await document_service.upload_documents(
                    "project-1",
                    [make_upload_file("重复.md", "# 重复".encode("utf-8"))],
                    actor,
                    mode="new",
                    document_name="重复需求",
                )

            self.assertEqual(caught.exception.detail["code"], "DOCUMENT_NAME_EXISTS")

    async def test_upload_requirement_rejects_archived_project(self):
        with isolated_document_store() as actor:
            with connect() as db:
                db.execute("UPDATE projects SET status = 'archived' WHERE id = 'project-1'")

            with self.assertRaises(HTTPException) as caught:
                await document_service.upload_documents(
                    "project-1",
                    [make_upload_file("归档项目需求.md", "# 归档项目需求".encode("utf-8"))],
                    actor,
                    mode="new",
                    document_name="归档项目需求",
                )

            self.assertEqual(caught.exception.detail["code"], "PROJECT_ARCHIVED")
            self.assertEqual(caught.exception.detail["message"], "归档项目不能上传需求。")

    def test_update_document_creates_new_markdown_version(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "versions" / "v1.md"
            markdown_path.parent.mkdir(parents=True)
            markdown_path.write_text("# 旧需求", encoding="utf-8")

            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '旧名称', 'PRD', 'docver-1', 'versioned', 'u-admin')
                    """
                )
                document_repo.create_version(
                    db,
                    version_id="docver-1",
                    document_id="doc-1",
                    version_no=1,
                    file_path=str(markdown_path),
                    source_action="merge",
                    change_summary="首次归并",
                    diff_summary="首次归并，无差异。",
                    created_by="u-admin",
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-1",
                    document_id="doc-1",
                    version_id="docver-1",
                    source_file_path="raw.docx",
                    original_filename="raw.docx",
                    file_format="docx",
                    markdown_file_path=str(markdown_path),
                    conversion_status="success",
                    mapping_status="merged",
                    conversion_summary="测试文件映射",
                    created_by="u-admin",
                )

            result = document_service.update_document(
                "project-1",
                "doc-1",
                SourceDocumentUpdateIn(name="新名称", markdown_content="# 新需求", change_summary="补充验收标准"),
                actor,
            )

            self.assertEqual(result["document"]["name"], "新名称")
            self.assertEqual(result["document"]["current_version"]["version_no"], 2)
            self.assertEqual(result["document"]["current_version"]["source_action"], "edit")
            self.assertEqual(result["document"]["current_version"]["change_summary"], "补充验收标准")
            self.assertEqual(result["markdown_content"], "# 新需求")
            self.assertEqual(
                Path(result["document"]["current_version"]["file_path"]).read_text(encoding="utf-8"),
                "# 新需求",
            )
            self.assertEqual([version["version_no"] for version in result["versions"]], [2, 1])

    def test_update_converted_markdown_updates_standard_file_without_creating_version(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "conversions" / "docmap-1.md"
            markdown_path.parent.mkdir(parents=True)
            markdown_path.write_text("# 旧标准文件", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-1",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="raw.md",
                    original_filename="raw.md",
                    file_format="md",
                    markdown_file_path=str(markdown_path),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="旧转换摘要",
                    created_by="u-admin",
                )

            result = document_service.update_converted_markdown(
                "docmap-1",
                markdown_content="# 新标准文件",
                change_summary="人工修订",
                actor=actor,
            )

            self.assertEqual(result["markdown_content"], "# 新标准文件")
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# 新标准文件")
            self.assertEqual(document_service.get_document_versions("doc-1"), [])

    def test_get_document_overview_returns_file_status_summary(self):
        with isolated_document_store() as actor:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-ready",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="ready.md",
                    original_filename="ready.md",
                    file_format="md",
                    markdown_file_path="ready.md",
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-failed",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="failed.pdf",
                    original_filename="failed.pdf",
                    file_format="pdf",
                    markdown_file_path=None,
                    conversion_status="failed",
                    mapping_status="pending_merge",
                    conversion_summary="失败",
                    created_by="u-admin",
                )

            overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(overview["document"]["name"], "登录需求")
            self.assertEqual(overview["stats"]["total_files"], 2)
            self.assertEqual(overview["stats"]["conversion_success"], 1)
            self.assertEqual(overview["stats"]["conversion_failed"], 1)
            self.assertEqual(overview["stats"]["mergeable_files"], 1)
            self.assertEqual(overview["has_open_conflicts"], False)
            statuses = {item["id"]: item["standard_file_status"] for item in overview["files"]}
            self.assertEqual(statuses["docmap-ready"], "ready")
            self.assertEqual(statuses["docmap-failed"], "failed")

    def test_get_document_overview_marks_missing_standard_file_as_generating(self):
        with isolated_document_store() as actor:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-generating",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="raw.pdf",
                    original_filename="raw.pdf",
                    file_format="pdf",
                    markdown_file_path=None,
                    conversion_status="processing",
                    mapping_status="pending_merge",
                    conversion_summary="正在生成标准文件",
                    created_by="u-admin",
                )

            overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(overview["files"][0]["standard_file_status"], "generating")

    def test_get_converted_markdown_retries_failed_pdf_mapping_when_source_exists(self):
        with isolated_document_store():
            source_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "raw" / "failed.pdf"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"%PDF-1.4")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-failed",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path=str(source_path),
                    original_filename="failed.pdf",
                    file_format="pdf",
                    markdown_file_path=None,
                    conversion_status="failed",
                    mapping_status="pending_merge",
                    conversion_summary="旧转换失败",
                    created_by="u-admin",
                )

            with patch("app.services.document_service.convert_requirement_file_to_markdown") as convert:
                convert.return_value = ("# PDF 标准文件\n", "重试转换成功")
                result = document_service.get_converted_markdown("docmap-failed")

            self.assertEqual(result["markdown_content"], "# PDF 标准文件\n")
            self.assertEqual(result["conversion_status"], "success")
            with connect() as db:
                row = document_repo.find_file_mapping(db, "docmap-failed")
            self.assertEqual(row["conversion_status"], "success")
            self.assertTrue(Path(row["markdown_file_path"]).exists())

    def test_merge_document_markdown_deduplicates_and_creates_initial_version(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "conversions"
            base_dir.mkdir(parents=True)
            first = base_dir / "first.md"
            second = base_dir / "second.md"
            first.write_text("# 登录\n\n- 支持账号登录\n- 支持退出", encoding="utf-8")
            second.write_text("# 登录补充\n\n- 支持账号登录\n- 支持验证码", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                for mapping_id, path, name in (("docmap-1", first, "first.md"), ("docmap-2", second, "second.md")):
                    document_repo.create_file_mapping(
                        db,
                        mapping_id=mapping_id,
                        document_id="doc-1",
                        version_id=None,
                        source_file_path=name,
                        original_filename=name,
                        file_format="md",
                        markdown_file_path=str(path),
                        conversion_status="success",
                        mapping_status="pending_merge",
                        conversion_summary="成功",
                        created_by="u-admin",
                    )

            result = document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "merged")
            self.assertIn("支持账号登录", result["markdown_content"])
            self.assertEqual(result["markdown_content"].count("支持账号登录"), 1)
            self.assertEqual(document_service.get_document_versions("doc-1")[0]["source_action"], "merge")

    def test_merge_document_markdown_returns_conflict_without_creating_version(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "conversions"
            base_dir.mkdir(parents=True)
            first = base_dir / "first.md"
            second = base_dir / "second.md"
            first.write_text("登录失败锁定次数：5次", encoding="utf-8")
            second.write_text("登录失败锁定次数：3次", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                for mapping_id, path, name in (("docmap-1", first, "first.md"), ("docmap-2", second, "second.md")):
                    document_repo.create_file_mapping(
                        db,
                        mapping_id=mapping_id,
                        document_id="doc-1",
                        version_id=None,
                        source_file_path=name,
                        original_filename=name,
                        file_format="md",
                        markdown_file_path=str(path),
                        conversion_status="success",
                        mapping_status="pending_merge",
                        conversion_summary="成功",
                        created_by="u-admin",
                    )

            result = document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "conflict")
            self.assertEqual(result["conflict_count"], 1)
            self.assertEqual(document_service.get_document_versions("doc-1"), [])

    def test_resolved_conflict_allows_merge_to_continue(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "conversions"
            base_dir.mkdir(parents=True)
            first = base_dir / "first.md"
            second = base_dir / "second.md"
            first.write_text("登录失败锁定次数：5次", encoding="utf-8")
            second.write_text("登录失败锁定次数：3次", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                for mapping_id, path, name in (("docmap-1", first, "first.md"), ("docmap-2", second, "second.md")):
                    document_repo.create_file_mapping(
                        db,
                        mapping_id=mapping_id,
                        document_id="doc-1",
                        version_id=None,
                        source_file_path=name,
                        original_filename=name,
                        file_format="md",
                        markdown_file_path=str(path),
                        conversion_status="success",
                        mapping_status="pending_merge",
                        conversion_summary="成功",
                        created_by="u-admin",
                    )

            conflict_result = document_service.merge_document_markdown("project-1", "doc-1", actor)
            conflict_id = conflict_result["conflicts"][0]["id"]
            document_service.resolve_document_conflict(
                "project-1",
                "doc-1",
                conflict_id,
                resolution="登录失败锁定次数：5次",
                resolution_type="manual",
                actor=actor,
            )
            merge_result = document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(merge_result["status"], "merged")
            self.assertIn("登录失败锁定次数：5次", merge_result["markdown_content"])


def make_upload_file(filename: str, content: bytes) -> TestUploadFile:
    return TestUploadFile(filename, content)


class TestUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class isolated_document_store:
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
                CREATE TABLE projects (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  status TEXT NOT NULL,
                  description TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE source_documents (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  document_type TEXT NOT NULL,
                  current_version_id TEXT,
                  status TEXT NOT NULL DEFAULT 'collecting',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(project_id, name)
                );
                CREATE TABLE source_document_versions (
                  id TEXT PRIMARY KEY,
                  document_id TEXT NOT NULL,
                  version_no INTEGER NOT NULL,
                  markdown_content TEXT NOT NULL DEFAULT '',
                  file_path TEXT NOT NULL,
                  source_action TEXT NOT NULL,
                  change_summary TEXT NOT NULL DEFAULT '',
                  diff_summary TEXT NOT NULL DEFAULT '',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(document_id, version_no)
                );
                CREATE TABLE source_document_file_mappings (
                  id TEXT PRIMARY KEY,
                  document_id TEXT NOT NULL,
                  version_id TEXT,
                  source_file_path TEXT NOT NULL,
                  original_filename TEXT NOT NULL,
                  file_format TEXT NOT NULL,
                  markdown_file_path TEXT,
                  conversion_status TEXT NOT NULL DEFAULT 'pending',
                  mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
                  conversion_summary TEXT NOT NULL DEFAULT '',
                  conversion_quality INTEGER,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE source_document_merge_conflicts (
                  id TEXT PRIMARY KEY,
                  document_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  source_file_names TEXT NOT NULL DEFAULT '',
                  fragment_a TEXT NOT NULL DEFAULT '',
                  fragment_b TEXT NOT NULL DEFAULT '',
                  resolution TEXT NOT NULL DEFAULT '',
                  resolution_type TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'open',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            db.execute("INSERT INTO projects (id, name, status) VALUES ('project-1', '项目A', 'active')")

        return {"id": "u-admin", "role": "admin"}

    def __exit__(self, exc_type, exc, tb):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
