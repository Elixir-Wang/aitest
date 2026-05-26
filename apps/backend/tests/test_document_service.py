from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.core.storage import resolve_stored_path
from app.repositories import document_repo
from app.schemas.document import SourceDocumentUpdateIn
from app.schemas.requirement_analysis import RequirementAnalysisOutput, RequirementQualityGate
from app.schemas.requirement_conversion import RequirementConversionOutput
from app.schemas.requirement_merge import RequirementCoverageItem, RequirementMergeConflictOut, RequirementMergeOutput
from app.services import document_service
from fastapi import HTTPException


class DocumentServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_conflict_table_exists_in_isolated_store(self):
        with isolated_document_store():
            with connect() as db:
                rows = db.execute("PRAGMA table_info(source_document_merge_conflicts)").fetchall()

        columns = {row["name"] for row in rows}
        self.assertIn("resolution", columns)
        self.assertIn("conflict_type", columns)
        self.assertIn("agent_suggestion", columns)

    def test_merge_support_tables_exist_in_isolated_store(self):
        with isolated_document_store():
            with connect() as db:
                merge_run_columns = {row["name"] for row in db.execute("PRAGMA table_info(requirement_merge_runs)").fetchall()}
                coverage_columns = {row["name"] for row in db.execute("PRAGMA table_info(requirement_source_coverage_items)").fetchall()}
                change_log_columns = {row["name"] for row in db.execute("PRAGMA table_info(document_version_change_logs)").fetchall()}
                analysis_columns = {row["name"] for row in db.execute("PRAGMA table_info(requirement_analyses)").fetchall()}

        self.assertIn("merge_mode", merge_run_columns)
        self.assertIn("affected_modules", merge_run_columns)
        self.assertIn("coverage_status", coverage_columns)
        self.assertIn("version_id", change_log_columns)
        self.assertIn("quality_result", analysis_columns)
        self.assertIn("testability_score", analysis_columns)

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
            self.assertEqual({item["conversion_status"] for item in result["files"]}, {"pending"})
            self.assertEqual(document_service.get_document_versions(result["document"]["id"]), [])

    async def test_convert_source_file_mapping_uses_format_converter_agent_result(self):
        with isolated_document_store() as actor:
            async def fake_agent_conversion(input_data):
                self.assertEqual(input_data.filename, "登录需求.md")
                self.assertEqual(input_data.candidate_markdown, "# 登录需求\n")
                return RequirementConversionOutput(
                    markdown_content="# 智能体标准化需求\n",
                    conversion_summary="智能体完成标准化。",
                    quality_score=98,
                )

            with patch(
                "app.services.document_file_service.convert_raw_requirement_format",
                fake_agent_conversion,
            ):
                result = await document_service.upload_documents(
                    "project-1",
                    [make_upload_file("登录需求.md", "# 登录需求".encode("utf-8"))],
                    actor,
                    mode="new",
                    document_name="登录需求",
                )

                file = await document_service.convert_source_file_mapping(result["files"][0]["id"])

            self.assertEqual(Path(file["markdown_file_path"]).read_text(encoding="utf-8"), "# 智能体标准化需求\n")
            self.assertEqual(file["conversion_summary"], "智能体完成标准化。")

    async def test_convert_source_file_mapping_falls_back_when_format_converter_agent_fails(self):
        with isolated_document_store() as actor:
            async def fake_agent_conversion(_input_data):
                raise RuntimeError("模型未配置")

            with patch(
                "app.services.document_file_service.convert_raw_requirement_format",
                fake_agent_conversion,
            ):
                result = await document_service.upload_documents(
                    "project-1",
                    [make_upload_file("登录需求.md", "# 登录需求".encode("utf-8"))],
                    actor,
                    mode="new",
                    document_name="登录需求",
                )

                file = await document_service.convert_source_file_mapping(result["files"][0]["id"])

            self.assertEqual(file["conversion_status"], "success")
            self.assertEqual(Path(file["markdown_file_path"]).read_text(encoding="utf-8"), "# 登录需求\n")
            self.assertIn("智能体不可用，已使用本地转换结果", file["conversion_summary"])

    async def test_upload_docx_keeps_original_file_and_creates_markdown(self):
        with isolated_document_store() as actor:
            result = await document_service.upload_documents(
                "project-1",
                [make_upload_file("原始需求.docx", b"docx-bytes")],
                actor,
                mode="new",
                document_name="原始需求",
            )

            file = result["files"][0]
            self.assertEqual(file["conversion_status"], "pending")
            self.assertIsNone(file["markdown_file_path"])
            self.assertIn("/raw/", file["source_file_path"])
            self.assertIsNone(file["preview_file_path"])
            self.assertEqual(Path(file["source_file_path"]).read_bytes(), b"docx-bytes")
            with connect() as db:
                row = document_repo.find_file_mapping(db, file["id"])
            self.assertFalse(Path(row["source_file_path"]).is_absolute())
            self.assertIsNone(row["markdown_file_path"])

    def test_resolves_legacy_windows_storage_path(self):
        with isolated_document_store():
            source_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "raw" / "legacy.docx"
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "markdown" / "conversions" / "legacy.md"
            source_path.parent.mkdir(parents=True)
            markdown_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"legacy-docx")
            markdown_path.write_text("# Legacy Markdown", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '旧路径需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-legacy",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="D:\\project\\test_project\\apps\\backend\\data\\projects\\project-1\\requirements\\doc-1\\raw\\legacy.docx",
                    original_filename="legacy.docx",
                    file_format="docx",
                    markdown_file_path="D:\\project\\test_project\\apps\\backend\\data\\projects\\project-1\\requirements\\doc-1\\markdown\\conversions\\legacy.md",
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="旧路径",
                    created_by="u-admin",
                )

            original = document_service.get_original_file("docmap-legacy")
            markdown = document_service.get_converted_markdown("docmap-legacy")

            self.assertEqual(Path(original["download_path"]).read_bytes(), b"legacy-docx")
            self.assertEqual(markdown["markdown_content"], "# Legacy Markdown")

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
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "versions" / "v1.md"
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
            self.assertIn("/versions/", result["document"]["current_version"]["file_path"])
            self.assertEqual(result["markdown_content"], "# 新需求")
            self.assertEqual(
                Path(result["document"]["current_version"]["file_path"]).read_text(encoding="utf-8"),
                "# 新需求",
            )
            self.assertEqual([version["version_no"] for version in result["versions"]], [2, 1])

    def test_update_converted_markdown_updates_standard_file_without_creating_version(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard" / "docmap-1.md"
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

    def test_update_converted_markdown_marks_merged_file_pending_merge(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard" / "docmap-1.md"
            version_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "versions" / "v1.md"
            markdown_path.parent.mkdir(parents=True)
            version_path.parent.mkdir(parents=True)
            markdown_path.write_text("# 旧标准文件", encoding="utf-8")
            version_path.write_text("# 初始需求", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', 'docver-1', 'versioned', 'u-admin')
                    """
                )
                document_repo.create_version(
                    db,
                    version_id="docver-1",
                    document_id="doc-1",
                    version_no=1,
                    file_path=str(version_path),
                    source_action="merge",
                    change_summary="初始合并",
                    diff_summary="",
                    created_by="u-admin",
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-1",
                    document_id="doc-1",
                    version_id="docver-1",
                    source_file_path="raw.md",
                    original_filename="raw.md",
                    file_format="md",
                    markdown_file_path=str(markdown_path),
                    conversion_status="success",
                    mapping_status="merged",
                    conversion_summary="旧转换摘要",
                    created_by="u-admin",
                )

            document_service.update_converted_markdown(
                "docmap-1",
                markdown_content="# 新标准文件",
                change_summary="人工修订",
                actor=actor,
            )
            overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(overview["merge_sync_status"], "outdated")
            self.assertEqual(overview["changed_standard_files"][0]["id"], "docmap-1")
            self.assertEqual(overview["files"][0]["mapping_status"], "pending_merge")
            self.assertIsNone(overview["files"][0]["version_id"])

    def test_delete_source_file_removes_converted_assets(self):
        with isolated_document_store() as actor:
            document_dir = Path(document_service.project_requirement_dir("project-1", "doc-1"))
            source_path = document_dir / "raw" / "docmap-1-raw.docx"
            markdown_path = document_dir / "standard" / "docmap-1.md"
            assets_dir = markdown_path.parent / "docmap-1_assets"
            source_path.parent.mkdir(parents=True)
            markdown_path.parent.mkdir(parents=True)
            assets_dir.mkdir(parents=True)
            source_path.write_bytes(b"raw")
            markdown_path.write_text("![image-1](docmap-1_assets/image-1.png)", encoding="utf-8")
            (assets_dir / "image-1.png").write_bytes(b"image")
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
                    source_file_path=str(source_path),
                    original_filename="raw.docx",
                    file_format="docx",
                    markdown_file_path=str(markdown_path),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )

            result = document_service.delete_source_file("docmap-1", actor)

            self.assertEqual(result, {"success": True})
            self.assertFalse(source_path.exists())
            self.assertFalse(markdown_path.exists())
            self.assertFalse(assets_dir.exists())

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

    async def test_convert_source_file_mapping_retries_failed_docx_mapping_when_source_exists(self):
        with isolated_document_store() as actor:
            source_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "raw" / "failed.docx"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"docx-bytes")
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
                    original_filename="failed.docx",
                    file_format="docx",
                    markdown_file_path=None,
                    conversion_status="failed",
                    mapping_status="pending_merge",
                    conversion_summary="旧转换失败",
                    created_by="u-admin",
                )

            async def fake_convert_to_markdown(*_args, **_kwargs):
                return "# DOCX 标准文件\n", "重试转换成功"

            with patch("app.services.document_file_service.convert_to_markdown", fake_convert_to_markdown):
                result = await document_service.convert_source_file_mapping("docmap-failed")
                overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(result["conversion_status"], "success")
            self.assertEqual(overview["stats"]["conversion_success"], 1)
            self.assertEqual(overview["stats"]["conversion_failed"], 0)
            self.assertEqual(overview["stats"]["mergeable_files"], 1)
            self.assertEqual(overview["files"][0]["conversion_status"], "success")
            self.assertEqual(overview["files"][0]["standard_file_status"], "ready")
            with connect() as db:
                row = document_repo.find_file_mapping(db, "docmap-failed")
            self.assertEqual(row["conversion_status"], "success")
            self.assertTrue(resolve_stored_path(row["markdown_file_path"]).exists())

    async def test_get_converted_markdown_does_not_retry_failed_pdf_mapping(self):
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

            with self.assertRaises(HTTPException) as caught:
                document_service.get_converted_markdown("docmap-failed")

            self.assertEqual(caught.exception.detail["code"], "DOCUMENT_CONVERSION_NOT_READY")
            with connect() as db:
                row = document_repo.find_file_mapping(db, "docmap-failed")
            self.assertEqual(row["conversion_status"], "failed")
            self.assertIsNone(row["markdown_file_path"])

    async def test_analyze_document_requirement_persists_latest_result(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "versions" / "v1.md"
            markdown_path.parent.mkdir(parents=True)
            markdown_path.write_text("# 登录需求\n\n- 支持账号登录", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', 'docver-1', 'versioned', 'u-admin')
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

            with patch("app.services.requirement_analysis_service.run_requirement_analysis") as analysis_agent:
                analysis_agent.return_value = RequirementAnalysisOutput(
                    status="completed",
                    analysis_summary="识别登录模块。",
                    quality_gate=RequirementQualityGate(
                        result="passed",
                        testability_score=90,
                        passed_checks=["模块识别完成"],
                    ),
                )
                result = await document_service.analyze_document_requirement("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["analysis_summary"], "识别登录模块。")
            latest = document_service.get_latest_requirement_analysis("project-1", "doc-1", actor)
            self.assertEqual(latest["analysis"]["quality_result"], "passed")
            self.assertEqual(latest["analysis"]["testability_score"], 90)
            self.assertEqual(latest["analysis"]["output"]["quality_gate"]["result"], "passed")

    async def test_analyze_document_requirement_blocks_open_conflicts(self):
        with isolated_document_store() as actor:
            markdown_path = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "versions" / "v1.md"
            markdown_path.parent.mkdir(parents=True)
            markdown_path.write_text("# 登录需求", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', 'docver-1', 'versioned', 'u-admin')
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
                document_repo.create_conflict(
                    db,
                    conflict_id="conflict-1",
                    document_id="doc-1",
                    title="锁定次数冲突",
                    source_file_names="a.md、b.md",
                    fragment_a="5次",
                    fragment_b="3次",
                )

            with self.assertRaises(HTTPException) as caught:
                await document_service.analyze_document_requirement("project-1", "doc-1", actor)

            self.assertEqual(caught.exception.detail["code"], "REQUIREMENT_ANALYSIS_CONFLICT_BLOCKED")

    async def test_merge_document_markdown_deduplicates_and_creates_initial_version(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
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

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="merged",
                    markdown_content="# 登录需求\n\n- 支持账号登录\n- 支持退出\n- 支持验证码",
                    merge_summary="已归并 2 个标准文件。",
                    source_file_ids=["docmap-1", "docmap-2"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-1",
                            source_excerpt="支持账号登录",
                            target_module="登录",
                            coverage_status="merged",
                            reason="合入登录需求。",
                        )
                    ],
                )
                result = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "merged")
            self.assertIn("version_id", result)
            self.assertIn("version_no", result)
            self.assertIn("merge_summary", result)
            self.assertIn("source_file_ids", result)
            self.assertIn("artifact_tabs", result)
            self.assertIn("machine_artifacts", result)
            self.assertIn("支持账号登录", result["markdown_content"])
            self.assertEqual(result["markdown_content"].count("支持账号登录"), 1)
            fragments_path = resolve_stored_path(result["machine_artifacts"]["fragments_path"])
            self.assertIsNotNone(fragments_path)
            self.assertTrue(fragments_path.exists())
            self.assertIn("frag-1-00001", fragments_path.read_text(encoding="utf-8"))
            self.assertEqual(document_service.get_document_versions("doc-1")[0]["source_action"], "merge")

    async def test_merge_document_markdown_returns_preview_when_draft_drops_most_content(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
            base_dir.mkdir(parents=True)
            source = base_dir / "long.md"
            source.write_text(
                "# 长需求\n\n"
                + "\n".join(f"- 支持独有业务规则 {index:02d}，需要在合并稿中保留。" for index in range(1, 31)),
                encoding="utf-8",
            )
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '长需求', 'PRD', NULL, 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-1",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="long.md",
                    original_filename="long.md",
                    file_format="md",
                    markdown_file_path=str(source),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="merged",
                    markdown_content="# 长需求\n\n## 需求概述\n\n- 支持主要业务规则。",
                    merge_summary="已归并 1 个标准文件。",
                    source_file_ids=["docmap-1"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-1",
                            source_excerpt="支持独有业务规则",
                            target_module="需求概述",
                            coverage_status="merged",
                            reason="智能体声称已合入。",
                        )
                    ],
                )
                result = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "preview")
            self.assertEqual(result["quality_result"], "failed")
            self.assertIn("疑似只生成摘要", result["artifact_tabs"][3]["content"])
            self.assertEqual(document_service.get_document_versions("doc-1"), [])

    async def test_merge_document_markdown_returns_conflict_without_creating_version(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
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

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="conflict",
                    markdown_content="",
                    merge_summary="发现锁定次数冲突。",
                    source_file_ids=["docmap-1", "docmap-2"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-1",
                            source_excerpt="登录失败锁定次数：5次",
                            coverage_status="conflict",
                            reason="与另一来源冲突。",
                        )
                    ],
                    conflicts=[
                        RequirementMergeConflictOut(
                            title="登录失败锁定次数不一致",
                            source_refs=[{"mapping_id": "docmap-1", "filename": "first.md"}],
                            fragment_a="登录失败锁定次数：5次",
                            fragment_b="登录失败锁定次数：3次",
                        )
                    ],
                )
                result = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "conflict")
            self.assertEqual(result["conflict_count"], 1)
            self.assertNotIn("artifact_tabs", result)
            self.assertNotIn("markdown_preview", result)
            self.assertIn("id", result["conflicts"][0])
            self.assertIn("title", result["conflicts"][0])
            self.assertIn("fragment_a", result["conflicts"][0])
            self.assertIn("fragment_b", result["conflicts"][0])
            self.assertEqual(result["conflicts"][0]["source_file_names"], "first")
            self.assertEqual(document_service.get_document_versions("doc-1"), [])

    async def test_resolved_conflict_allows_merge_to_continue(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
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

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="conflict",
                    merge_summary="发现锁定次数冲突。",
                    source_file_ids=["docmap-1", "docmap-2"],
                    conflicts=[
                        RequirementMergeConflictOut(
                            title="登录失败锁定次数不一致",
                            source_refs=[{"mapping_id": "docmap-1", "filename": "first.md"}],
                            fragment_a="登录失败锁定次数：5次",
                            fragment_b="登录失败锁定次数：3次",
                        )
                    ],
                )
                conflict_result = await document_service.merge_document_markdown("project-1", "doc-1", actor)
            conflict_id = conflict_result["conflicts"][0]["id"]
            document_service.resolve_document_conflict(
                "project-1",
                "doc-1",
                conflict_id,
                resolution="登录失败锁定次数：5次",
                resolution_type="manual",
                actor=actor,
            )
            with connect() as db:
                conflict_log = db.execute(
                    """
                    SELECT module, action, object_type, object_id, project_id
                    FROM operation_logs
                    WHERE object_id = ? AND action = 'resolve_conflict'
                    """,
                    (conflict_id,),
                ).fetchone()
            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="merged",
                    markdown_content="# 登录需求\n\n- 登录失败锁定次数：5次",
                    merge_summary="按人工决策归并。",
                    source_file_ids=["docmap-1", "docmap-2"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-1",
                            source_excerpt="登录失败锁定次数：5次",
                            target_module="登录安全",
                            coverage_status="merged",
                            reason="按人工决策合入。",
                        )
                    ],
                )
                merge_result = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(merge_result["status"], "merged")
            self.assertIn("登录失败锁定次数：5次", merge_result["markdown_content"])
            self.assertEqual(conflict_log["module"], "requirement")
            self.assertEqual(conflict_log["object_type"], "requirement_conflict")
            self.assertEqual(conflict_log["project_id"], "project-1")

    async def test_resolve_conflict_writes_operation_log(self):
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
                document_repo.create_conflict(
                    db,
                    conflict_id="conflict-1",
                    run_id="mergerun-1",
                    document_id="doc-1",
                    title="登录失败锁定次数不一致",
                    source_file_names="first, second",
                    fragment_a="5次",
                    fragment_b="3次",
                )

            result = document_service.resolve_document_conflict(
                "project-1",
                "doc-1",
                "conflict-1",
                resolution="登录失败锁定次数：5次",
                resolution_type="manual",
                actor=actor,
            )

            with connect() as db:
                row = db.execute(
                    """
                    SELECT module, action, object_type, object_id, project_id
                    FROM operation_logs
                    WHERE object_id = 'conflict-1'
                    """
                ).fetchone()

            self.assertFalse(result["has_open_conflicts"])
            self.assertEqual(row["module"], "requirement")
            self.assertEqual(row["action"], "resolve_conflict")
            self.assertEqual(row["object_type"], "requirement_conflict")
            self.assertEqual(row["project_id"], "project-1")

    async def test_incremental_merge_returns_preview_and_confirm_creates_version(self):
        with isolated_document_store() as actor:
            version_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "versions"
            conversion_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
            version_dir.mkdir(parents=True)
            conversion_dir.mkdir(parents=True)
            current = version_dir / "v1.md"
            addition = conversion_dir / "addition.md"
            current.write_text("# 登录需求\n\n- 支持账号登录", encoding="utf-8")
            addition.write_text("# 登录补充\n\n- 支持验证码", encoding="utf-8")
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO source_documents
                      (id, project_id, name, document_type, current_version_id, status, created_by)
                    VALUES
                      ('doc-1', 'project-1', '登录需求', 'PRD', 'docver-1', 'pending_merge', 'u-admin')
                    """
                )
                document_repo.create_version(
                    db,
                    version_id="docver-1",
                    document_id="doc-1",
                    version_no=1,
                    file_path=str(current),
                    source_action="merge",
                    change_summary="首次归并",
                    diff_summary="首次归并。",
                    created_by="u-admin",
                )
                document_repo.create_file_mapping(
                    db,
                    mapping_id="docmap-2",
                    document_id="doc-1",
                    version_id=None,
                    source_file_path="addition.md",
                    original_filename="addition.md",
                    file_format="md",
                    markdown_file_path=str(addition),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="preview",
                    markdown_preview="# 登录需求\n\n- 支持账号登录\n- 支持验证码",
                    merge_summary="生成增量预览。",
                    source_file_ids=["docmap-2"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-2",
                            source_excerpt="支持验证码",
                            target_module="登录",
                            coverage_status="merged",
                            reason="合入登录补充。",
                        )
                    ],
                )
                preview = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(preview["status"], "preview")
            self.assertIn("preview_id", preview)
            self.assertIn("artifact_tabs", preview)
            self.assertEqual([version["version_no"] for version in document_service.get_document_versions("doc-1")], [1])

            confirmed = await document_service.merge_document_markdown(
                "project-1",
                "doc-1",
                actor,
                confirm_preview_id=preview["preview_id"],
            )

            self.assertEqual(confirmed["status"], "merged")
            self.assertEqual(confirmed["version_no"], 2)
            self.assertIn("支持验证码", confirmed["markdown_content"])
            self.assertEqual([version["version_no"] for version in document_service.get_document_versions("doc-1")], [2, 1])

    async def test_document_overview_returns_latest_merge_artifact_tabs(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
            base_dir.mkdir(parents=True)
            source = base_dir / "source.md"
            source.write_text("# 登录需求\n\n- 支持账号登录", encoding="utf-8")
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
                    source_file_path="source.md",
                    original_filename="source.md",
                    file_format="md",
                    markdown_file_path=str(source),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.return_value = RequirementMergeOutput(
                    status="merged",
                    markdown_content="# 登录需求\n\n- 支持账号登录",
                    merge_summary="已归并 1 个标准文件。",
                    source_file_ids=["docmap-1"],
                    coverage_items=[
                        RequirementCoverageItem(
                            mapping_id="docmap-1",
                            source_excerpt="支持账号登录",
                            target_module="登录",
                            coverage_status="merged",
                            reason="合入登录需求。",
                        )
                    ],
                )
                await document_service.merge_document_markdown("project-1", "doc-1", actor)

            overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(
                [tab["key"] for tab in overview["artifact_tabs"]],
                ["preview", "mapping", "conflicts", "report"],
            )
            self.assertIn("支持账号登录", overview["artifact_tabs"][0]["content"])
            self.assertIn("段落映射", overview["artifact_tabs"][1]["content"])
            self.assertIn("明显冲突", overview["artifact_tabs"][2]["content"])
            self.assertIn("归并质量报告", overview["artifact_tabs"][3]["content"])

    async def test_merge_agent_failure_writes_visible_failure_artifacts(self):
        with isolated_document_store() as actor:
            base_dir = Path(document_service.project_requirement_dir("project-1", "doc-1")) / "standard"
            base_dir.mkdir(parents=True)
            source = base_dir / "source.md"
            source.write_text("# 登录需求\n\n- 支持账号登录", encoding="utf-8")
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
                    source_file_path="source.md",
                    original_filename="source.md",
                    file_format="md",
                    markdown_file_path=str(source),
                    conversion_status="success",
                    mapping_status="pending_merge",
                    conversion_summary="成功",
                    created_by="u-admin",
                )

            with patch("app.services.requirement_merge_service.run_requirement_merge_v2") as merge_agent:
                merge_agent.side_effect = RuntimeError("model not configured")
                result = await document_service.merge_document_markdown("project-1", "doc-1", actor)

            self.assertEqual(result["status"], "preview")
            self.assertEqual(result["quality_result"], "failed")
            self.assertIn("model not configured", result["merge_summary"])
            self.assertIn("合并候选稿未生成", result["markdown_preview"])
            self.assertEqual(document_service.get_document_versions("doc-1"), [])
            overview = document_service.get_document_overview("project-1", "doc-1", actor)

            self.assertEqual(
                [tab["key"] for tab in overview["artifact_tabs"]],
                ["preview", "mapping", "conflicts", "report"],
            )
            self.assertIn("合并候选稿未生成", overview["artifact_tabs"][0]["content"])
            self.assertIn("model not configured", overview["artifact_tabs"][3]["content"])

    async def test_merge_exception_writes_failed_operation_log(self):
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

            with patch("app.services.document_merge_orchestrator.merge_document_markdown") as merge_orchestrator:
                merge_orchestrator.side_effect = HTTPException(
                    status_code=502,
                    detail={"code": "DOCUMENT_MERGE_AGENT_FAILED", "message": "需求归并智能体运行失败：模型超时"},
                )
                with self.assertRaises(HTTPException):
                    await document_service.merge_document_markdown("project-1", "doc-1", actor)

            with connect() as db:
                row = db.execute(
                    """
                    SELECT module, action, result, failure_reason, summary
                    FROM operation_logs
                    WHERE object_id = 'doc-1'
                    """
                ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row["module"], "requirement")
            self.assertEqual(row["action"], "merge")
            self.assertEqual(row["result"], "failed")
            self.assertIn("模型超时", row["failure_reason"])


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
                CREATE TABLE model_providers (
                  id TEXT PRIMARY KEY,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  base_url TEXT NOT NULL DEFAULT '',
                  api_key TEXT NOT NULL DEFAULT '',
                  description TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'enabled',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE agent_model_assignments (
                  agent_id TEXT PRIMARY KEY,
                  model_provider_id TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                  preview_file_path TEXT,
                  conversion_status TEXT NOT NULL DEFAULT 'pending',
                  mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
                  conversion_summary TEXT NOT NULL DEFAULT '',
                  conversion_quality INTEGER,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE source_document_merge_conflicts (
                  id TEXT PRIMARY KEY,
                  run_id TEXT,
                  document_id TEXT NOT NULL,
                  conflict_type TEXT NOT NULL DEFAULT 'contradiction',
                  severity TEXT NOT NULL DEFAULT 'medium',
                  title TEXT NOT NULL,
                  source_refs TEXT NOT NULL DEFAULT '[]',
                  source_file_names TEXT NOT NULL DEFAULT '',
                  fragment_a TEXT NOT NULL DEFAULT '',
                  fragment_b TEXT NOT NULL DEFAULT '',
                  agent_suggestion TEXT NOT NULL DEFAULT '',
                  resolution TEXT NOT NULL DEFAULT '',
                  resolution_type TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'open',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE requirement_merge_runs (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  document_id TEXT NOT NULL,
                  base_version_id TEXT,
                  output_version_id TEXT,
                  merge_mode TEXT NOT NULL,
                  status TEXT NOT NULL,
                  input_mapping_ids TEXT NOT NULL DEFAULT '[]',
                  resolved_conflict_ids TEXT NOT NULL DEFAULT '[]',
                  merge_summary TEXT NOT NULL DEFAULT '',
                  diff_summary TEXT NOT NULL DEFAULT '',
                  affected_modules TEXT NOT NULL DEFAULT '[]',
                  output_preview_path TEXT,
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  finished_at TEXT
                );
                CREATE TABLE requirement_source_coverage_items (
                  id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  document_id TEXT NOT NULL,
                  version_id TEXT,
                  mapping_id TEXT NOT NULL,
                  source_heading TEXT NOT NULL DEFAULT '',
                  source_excerpt TEXT NOT NULL DEFAULT '',
                  target_module TEXT NOT NULL DEFAULT '',
                  target_heading TEXT NOT NULL DEFAULT '',
                  coverage_status TEXT NOT NULL,
                  reason TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE document_version_change_logs (
                  id TEXT PRIMARY KEY,
                  document_id TEXT NOT NULL,
                  version_id TEXT NOT NULL,
                  source_action TEXT NOT NULL,
                  change_summary TEXT NOT NULL DEFAULT '',
                  diff_summary TEXT NOT NULL DEFAULT '',
                  affected_modules TEXT NOT NULL DEFAULT '[]',
                  source_mapping_ids TEXT NOT NULL DEFAULT '[]',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE requirement_analyses (
                  id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  document_id TEXT NOT NULL,
                  version_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  analysis_summary TEXT NOT NULL DEFAULT '',
                  output_json TEXT NOT NULL,
                  quality_result TEXT NOT NULL,
                  testability_score INTEGER NOT NULL DEFAULT 0,
                  created_by TEXT NOT NULL,
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
            db.execute("INSERT INTO projects (id, name, status) VALUES ('project-1', '项目A', 'active')")

        return {"id": "u-admin", "role": "admin"}

    def __exit__(self, exc_type, exc, tb):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
