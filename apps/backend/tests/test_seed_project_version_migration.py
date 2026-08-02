import sqlite3

from app.seed.schema import CREATE_SCHEMA_SQL
from app.seed.seeds import _ensure_project_version_structure


def test_project_version_migration_upgrades_legacy_document_tables() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
          description TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          code TEXT NOT NULL DEFAULT '',
          default_site_url TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL DEFAULT 'system'
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
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          UNIQUE(project_id, name)
        );

        INSERT INTO projects (id, name, status, created_by)
        VALUES ('project-1', 'Legacy project', 'active', 'user-1');
        INSERT INTO source_documents (
          id, project_id, name, document_type, status, created_by
        ) VALUES (
          'document-1', 'project-1', 'Legacy requirement', 'PRD', 'ready', 'user-1'
        );
        """
    )

    db.executescript(CREATE_SCHEMA_SQL)
    _ensure_project_version_structure(db)

    project = db.execute(
        "SELECT default_version_id FROM projects WHERE id = 'project-1'"
    ).fetchone()
    document = db.execute(
        "SELECT project_version_id FROM source_documents WHERE id = 'document-1'"
    ).fetchone()
    version = db.execute(
        "SELECT id, version FROM project_versions WHERE project_id = 'project-1'"
    ).fetchone()

    assert version["version"] == "1.0.0"
    assert project["default_version_id"] == version["id"]
    assert document["project_version_id"] == version["id"]
    assert db.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type = 'index' AND name = 'idx_source_documents_project_version'"
    ).fetchone()
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
