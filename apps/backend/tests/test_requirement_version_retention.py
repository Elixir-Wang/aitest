from pathlib import Path


ACTOR = {
    "id": "u-admin",
    "role": "admin",
    "nickname": "管理员",
    "username": "admin",
    "project_scope": "全部项目",
}


def test_prune_document_versions_keeps_latest_five_and_deletes_oldest_files(monkeypatch, tmp_path):
    from app.core import db as core_db
    from app.core import storage as core_storage
    from app.seed.init_db import init_db
    from app.services.document.version_retention import delete_pruned_version_files, prune_document_versions

    data_dir = tmp_path / "data"
    project_storage = data_dir / "projects"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(core_storage, "PROJECT_FILE_STORAGE_ROOT", project_storage)
    init_db()

    versions_dir = project_storage / "project-1" / "requirements" / "doc-1" / "versions"
    versions_dir.mkdir(parents=True)
    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-1', 'project-1', '登录需求', 'PRD', 'versioned', 'u-admin')
            """
        )
        for version_no in range(1, 7):
            version_path = versions_dir / f"v{version_no}.md"
            version_path.write_text(f"# 版本 {version_no}\n", encoding="utf-8")
            db.execute(
                """
                INSERT INTO source_document_versions
                  (id, document_id, version_no, file_path, source_action, created_by)
                VALUES (?, 'doc-1', ?, ?, 'edit', 'u-admin')
                """,
                (f"version-{version_no}", version_no, f"project-1/requirements/doc-1/versions/v{version_no}.md"),
            )

        pruned_paths = prune_document_versions(db, "doc-1")

    delete_pruned_version_files(pruned_paths)

    with core_db.connect() as db:
        versions = db.execute(
            "SELECT version_no FROM source_document_versions WHERE document_id = 'doc-1' ORDER BY version_no"
        ).fetchall()
        next_version_no = db.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS value FROM source_document_versions WHERE document_id = 'doc-1'"
        ).fetchone()["value"]

    assert [row["version_no"] for row in versions] == [2, 3, 4, 5, 6]
    assert next_version_no == 7
    assert not (versions_dir / "v1.md").exists()
    assert all((versions_dir / f"v{version_no}.md").exists() for version_no in range(2, 7))
    assert pruned_paths == [Path(versions_dir / "v1.md")]


def test_update_document_automatically_prunes_oldest_version(monkeypatch, tmp_path):
    from app.core import db as core_db
    from app.core import storage as core_storage
    from app.schemas.document import SourceDocumentUpdateIn
    from app.seed.init_db import init_db
    from app.services.document.documents import update_document

    data_dir = tmp_path / "data"
    project_storage = data_dir / "projects"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(core_storage, "PROJECT_FILE_STORAGE_ROOT", project_storage)
    init_db()

    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES ('doc-1', 'project-1', '登录需求', 'PRD', 'collecting', 'u-admin')
            """
        )

    for version_no in range(1, 7):
        result = update_document(
            "project-1",
            "doc-1",
            SourceDocumentUpdateIn(
                name="登录需求",
                markdown_content=f"# 版本 {version_no}",
                change_summary=f"保存版本 {version_no}",
            ),
            ACTOR,
        )

    assert [version["version_no"] for version in result["versions"]] == [6, 5, 4, 3, 2]
    versions_dir = project_storage / "project-1" / "requirements" / "doc-1" / "versions"
    assert not (versions_dir / "v1.md").exists()
    assert (versions_dir / "v6.md").read_text(encoding="utf-8") == "# 版本 6"
