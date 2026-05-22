from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.repositories import document_repo
from app.schemas.document import SourceDocumentUpdateIn
from app.services import document_service


class DocumentServiceTest(unittest.TestCase):
    def test_update_document_creates_new_markdown_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "ai_testing.db"
            storage_root = temp_path / "projects"

            with (
                patch("app.core.db.DB_PATH", db_path),
                patch("app.core.db.DATA_DIR", temp_path),
                patch("app.core.storage.PROJECT_FILE_STORAGE_ROOT", storage_root),
            ):
                actor = {"id": "u-admin", "role": "admin"}
                markdown_path = storage_root / "project-1" / "requirements" / "doc-1" / "markdown" / "v1.md"
                markdown_path.parent.mkdir(parents=True)
                markdown_path.write_text("# 旧需求", encoding="utf-8")

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
                          original_file_path TEXT NOT NULL,
                          current_version_id TEXT,
                          status TEXT NOT NULL DEFAULT 'uploaded',
                          created_by TEXT NOT NULL,
                          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                        """
                    )
                    db.execute("INSERT INTO projects (id, name, status) VALUES ('project-1', '项目A', 'active')")
                    db.execute(
                        """
                        INSERT INTO source_documents
                          (id, project_id, name, document_type, original_file_path, current_version_id, status, created_by)
                        VALUES
                          ('doc-1', 'project-1', '旧名称', 'PRD', 'raw.docx', 'docver-1', 'pending_review', 'u-admin')
                        """
                    )
                    document_repo.create_version(
                        db,
                        version_id="docver-1",
                        document_id="doc-1",
                        version_no=1,
                        file_path=str(markdown_path),
                        source_action="upload",
                        change_summary="首次上传",
                        diff_summary="首次上传，无差异。",
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


if __name__ == "__main__":
    unittest.main()
