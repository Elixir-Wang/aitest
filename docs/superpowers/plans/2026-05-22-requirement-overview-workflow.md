# Requirement Overview Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the requirement overview workflow with overview, original file, standard file, initial requirement, and conditional conflict handling tabs.

**Architecture:** Extend the existing document service and requirement detail route instead of creating a new workflow. Backend adds deterministic service boundaries for overview, standard Markdown edits, merge, and conflicts; frontend reuses the current requirement detail page, `MarkdownPreview`, shadcn tabs, tables, badges, textareas, and buttons.

**Tech Stack:** FastAPI, SQLite, Python unittest, Next.js App Router, React, shadcn/ui, lucide-react, Biome.

---

## File Structure

- Modify `apps/backend/app/seed/init_db.py`
  - Add `source_document_merge_conflicts` table.
  - Add migration helper for the conflict table.

- Modify `apps/backend/app/repositories/document_repo.py`
  - Add standard Markdown update helpers.
  - Add current document overview query helpers.
  - Add conflict CRUD helpers.
  - Add file mapping status updates after merge.

- Modify `apps/backend/app/services/document_service.py`
  - Add `get_document_overview`.
  - Add `update_converted_markdown`.
  - Add deterministic `merge_document_markdown`.
  - Add `list_document_conflicts` and `resolve_document_conflict`.
  - Keep `update_document` as the explicit formal version edit path.

- Modify `apps/backend/app/api/v1/requirements.py`
  - Add overview, merge, conflict, and standard Markdown save routes.

- Modify `apps/backend/app/schemas/document.py`
  - Add `SourceMarkdownUpdateIn` and `ConflictResolutionIn`.

- Modify `apps/backend/tests/test_document_service.py`
  - Add service tests for standard Markdown save, overview stats, merge success, conflict detection, conflict resolution, and successful re-merge.

- Create `apps/frontend/src/components/ai-testing/requirement-file-switcher.tsx`
  - Shared file switcher for original and standard file tabs.

- Modify `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
  - Replace old `当前工作稿 / 来源文件 / 版本记录` tabs with `概览 / 原始文件 / 标准文件 / 初始需求` plus conditional `冲突处理`.
  - Remove the in-page version records table.
  - Add inline standard Markdown editing and merge/conflict flow.

---

## Task 1: Add Backend Conflict Storage

**Files:**
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Add a failing test for conflict storage availability**

Add this test to `DocumentServiceTest`:

```python
def test_conflict_table_exists_in_isolated_store(self):
    with isolated_document_store():
        with connect() as db:
            rows = db.execute("PRAGMA table_info(source_document_merge_conflicts)").fetchall()

    self.assertIn("resolution", {row["name"] for row in rows})
```

- [ ] **Step 2: Update the isolated test schema**

In `isolated_document_store.__enter__`, add this table to the `db.executescript` block:

```sql
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
```

- [ ] **Step 3: Add the production table**

In `init_db()`, add this `CREATE TABLE IF NOT EXISTS` statement after `source_document_file_mappings`:

```sql
CREATE TABLE IF NOT EXISTS source_document_merge_conflicts (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  title TEXT NOT NULL,
  source_file_names TEXT NOT NULL DEFAULT '',
  fragment_a TEXT NOT NULL DEFAULT '',
  fragment_b TEXT NOT NULL DEFAULT '',
  resolution TEXT NOT NULL DEFAULT '',
  resolution_type TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('open', 'resolved')) DEFAULT 'open',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE
);
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: tests pass after Step 2 and Step 3.

- [ ] **Step 5: Commit**

```powershell
git add apps/backend/app/seed/init_db.py apps/backend/tests/test_document_service.py
git commit -m "feat: add requirement merge conflict storage"
```

---

## Task 2: Add Repository Helpers

**Files:**
- Modify: `apps/backend/app/repositories/document_repo.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Add repository helper tests through service-level tests**

Add tests in later service tasks first; do not expose repository tests separately. This task implements helpers needed by those service tests.

- [ ] **Step 2: Add Markdown path update helper**

Add to `document_repo.py`:

```python
def update_file_mapping_markdown(db: Connection, mapping_id: str, markdown_file_path: str, conversion_summary: str) -> None:
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET markdown_file_path = ?,
            conversion_status = 'success',
            conversion_summary = ?,
            conversion_quality = 100
        WHERE id = ?
        """,
        (markdown_file_path, conversion_summary, mapping_id),
    )
```

- [ ] **Step 3: Add merge mapping update helper**

Add:

```python
def mark_file_mappings_merged(db: Connection, document_id: str, version_id: str) -> None:
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET version_id = ?, mapping_status = 'merged'
        WHERE document_id = ?
          AND conversion_status IN ('success', 'warning')
          AND mapping_status != 'discarded'
        """,
        (version_id, document_id),
    )
```

- [ ] **Step 4: Add conflict helpers**

Add:

```python
def list_conflicts(db: Connection, document_id: str, *, status: str | None = None) -> list[Row]:
    if status:
        return db.execute(
            "SELECT * FROM source_document_merge_conflicts WHERE document_id = ? AND status = ? ORDER BY created_at DESC, id DESC",
            (document_id, status),
        ).fetchall()
    return db.execute(
        "SELECT * FROM source_document_merge_conflicts WHERE document_id = ? ORDER BY created_at DESC, id DESC",
        (document_id,),
    ).fetchall()


def create_conflict(
    db: Connection,
    *,
    conflict_id: str,
    document_id: str,
    title: str,
    source_file_names: str,
    fragment_a: str,
    fragment_b: str,
) -> None:
    db.execute(
        """
        INSERT INTO source_document_merge_conflicts
          (id, document_id, title, source_file_names, fragment_a, fragment_b, status)
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """,
        (conflict_id, document_id, title, source_file_names, fragment_a, fragment_b),
    )


def resolve_conflict(db: Connection, conflict_id: str, resolution: str, resolution_type: str) -> None:
    db.execute(
        """
        UPDATE source_document_merge_conflicts
        SET resolution = ?, resolution_type = ?, status = 'resolved', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (resolution, resolution_type, conflict_id),
    )


def close_open_conflicts(db: Connection, document_id: str) -> None:
    db.execute(
        """
        UPDATE source_document_merge_conflicts
        SET status = 'resolved', updated_at = CURRENT_TIMESTAMP
        WHERE document_id = ? AND status = 'open'
        """,
        (document_id,),
    )
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: existing tests still pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/backend/app/repositories/document_repo.py
git commit -m "feat: add requirement merge repository helpers"
```

---

## Task 3: Add Standard Markdown Save Service

**Files:**
- Modify: `apps/backend/app/schemas/document.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write failing test**

Add:

```python
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
```

- [ ] **Step 2: Add schema**

Add to `schemas/document.py`:

```python
class SourceMarkdownUpdateIn(BaseModel):
    markdown_content: str = ""
    change_summary: str = ""
```

- [ ] **Step 3: Implement service**

Add to `document_service.py`:

```python
def update_converted_markdown(mapping_id: str, *, markdown_content: str, change_summary: str, actor) -> dict:
    _ = actor
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        markdown_path_value = row["markdown_file_path"]
        if not markdown_path_value:
            document_dir = project_requirement_dir(row["project_id"], row["document_id"])
            markdown_path = document_dir / "markdown" / "conversions" / f"{mapping_id}.md"
        else:
            markdown_path = Path(markdown_path_value)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown_content, encoding="utf-8")
        summary = change_summary.strip() or "人工修订标准文件。"
        document_repo.update_file_mapping_markdown(db, mapping_id, str(markdown_path), summary)
    return get_converted_markdown(mapping_id)
```

- [ ] **Step 4: Add route**

Modify import:

```python
from app.schemas.document import SourceDocumentUpdateIn, SourceMarkdownUpdateIn
```

Add under the existing markdown GET route:

```python
@file_router.put("/{mapping_id}/markdown")
def update_requirement_markdown_file(
    mapping_id: str,
    payload: SourceMarkdownUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.update_converted_markdown(
        mapping_id,
        markdown_content=payload.markdown_content,
        change_summary=payload.change_summary,
        actor=actor,
    )
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: new test passes and no version is created.

- [ ] **Step 6: Commit**

```powershell
git add apps/backend/app/schemas/document.py apps/backend/app/services/document_service.py apps/backend/app/api/v1/requirements.py apps/backend/tests/test_document_service.py
git commit -m "feat: save requirement standard markdown"
```

---

## Task 4: Add Overview Service and Route

**Files:**
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write failing test**

Add:

```python
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
```

- [ ] **Step 2: Add serializer helpers**

Add:

```python
def _standard_file_status(row) -> str:
    if row["conversion_status"] == CONVERSION_FAILED_STATUS:
        return "failed"
    if not row["markdown_file_path"]:
        return "not_generated"
    summary = row["conversion_summary"] or ""
    if "人工修订" in summary:
        return "edited"
    return "ready"
```

- [ ] **Step 3: Implement overview service**

Add:

```python
def get_document_overview(project_id: str, document_id: str, actor) -> dict:
    detail = get_document_detail(project_id, document_id, actor)
    files = list_document_files(project_id, document_id)
    with connect() as db:
        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")

    stats = {
        "total_files": len(files),
        "conversion_success": sum(1 for item in files if item["conversion_status"] == "success"),
        "conversion_warning": sum(1 for item in files if item["conversion_status"] == "warning"),
        "conversion_failed": sum(1 for item in files if item["conversion_status"] == "failed"),
        "mergeable_files": sum(
            1
            for item in files
            if item["conversion_status"] in {"success", "warning"} and item["mapping_status"] != "discarded"
        ),
        "open_conflicts": len(open_conflicts),
        "initial_requirement_status": "generated" if detail["document"]["current_version_id"] else "not_generated",
    }

    overview_files = [
        {
            **item,
            "standard_file_status": _standard_file_status(item),
            "conflict_status": "open" if open_conflicts else "none",
        }
        for item in files
    ]

    return {
        "document": detail["document"],
        "stats": stats,
        "files": overview_files,
        "has_open_conflicts": len(open_conflicts) > 0,
        "initial_markdown_content": detail["markdown_content"],
    }
```

- [ ] **Step 4: Add route before `/{document_id}`**

Add in `requirements.py` before the detail route:

```python
@router.get("/{document_id}/overview")
def get_requirement_overview(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_document_overview(project_id, document_id, actor)
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: overview test passes.

- [ ] **Step 6: Commit**

```powershell
git add apps/backend/app/services/document_service.py apps/backend/app/api/v1/requirements.py apps/backend/tests/test_document_service.py
git commit -m "feat: add requirement overview endpoint"
```

---

## Task 5: Add Deterministic Merge and Conflict Service

**Files:**
- Modify: `apps/backend/app/schemas/document.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write merge success test**

Add:

```python
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
```

- [ ] **Step 2: Write conflict test**

Add:

```python
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
```

- [ ] **Step 3: Add conflict schema**

Add:

```python
class ConflictResolutionIn(BaseModel):
    resolution: str = Field(min_length=1)
    resolution_type: str = "manual"
```

- [ ] **Step 4: Implement merge service**

Add deterministic helpers to `document_service.py`:

```python
def merge_document_markdown(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        existing = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not existing:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        files = [
            row
            for row in document_repo.list_file_mappings(db, document_id)
            if row["conversion_status"] in {"success", "warning"} and row["mapping_status"] != "discarded"
        ]
        if not files:
            raise api_error(409, "DOCUMENT_MERGE_NO_FILES", "暂无可合并的标准文件。")

        open_conflicts = document_repo.list_conflicts(db, document_id, status="open")
        if open_conflicts:
            return {
                "status": "conflict",
                "conflict_count": len(open_conflicts),
                "conflicts": [_serialize_conflict(row) for row in open_conflicts],
            }

        contents = []
        for file_row in files:
            markdown_path = Path(file_row["markdown_file_path"])
            contents.append((file_row["id"], file_row["original_filename"], markdown_path.read_text(encoding="utf-8")))

        detected_conflict = _detect_simple_conflict(contents)
        if detected_conflict:
            conflict_id = f"conflict-{secrets.token_hex(8)}"
            document_repo.create_conflict(db, conflict_id=conflict_id, document_id=document_id, **detected_conflict)
            conflict_row = document_repo.list_conflicts(db, document_id, status="open")[0]
            return {"status": "conflict", "conflict_count": 1, "conflicts": [_serialize_conflict(conflict_row)]}

        merged_markdown = _merge_markdown_contents(existing["name"], contents)
        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        markdown_path = project_requirement_dir(project_id, document_id) / "markdown" / "versions" / f"v{version_no}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(merged_markdown, encoding="utf-8")
        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=str(markdown_path),
            source_action="merge",
            change_summary="生成初始需求",
            diff_summary=f"合并 {len(contents)} 个标准文件。",
            created_by=actor["id"],
        )
        document_repo.mark_file_mappings_merged(db, document_id, version_id)
        document_repo.close_open_conflicts(db, document_id)
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    return {
        "status": "merged",
        "version_id": version_id,
        "version_no": version_no,
        "markdown_content": merged_markdown,
        "merge_summary": f"已合并 {len(contents)} 个标准文件。",
        "source_file_ids": [item[0] for item in contents],
    }
```

Add simple helper implementations:

```python
def _merge_markdown_contents(document_name: str, contents: list[tuple[str, str, str]]) -> str:
    seen: set[str] = set()
    lines = [f"# {document_name}", "", "## 合并需求"]
    for _mapping_id, filename, markdown in contents:
        lines.extend(["", f"### 来源：{filename}"])
        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            normalized = line.lstrip("-*0123456789.、 ").strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            lines.append(f"- {normalized}")
    return "\n".join(lines).strip() + "\n"


def _detect_simple_conflict(contents: list[tuple[str, str, str]]) -> dict | None:
    lock_lines = [(filename, line.strip()) for _id, filename, markdown in contents for line in markdown.splitlines() if "锁定次数" in line]
    if len({line for _filename, line in lock_lines}) > 1:
        return {
            "title": "锁定次数不一致",
            "source_file_names": "、".join(filename for filename, _line in lock_lines),
            "fragment_a": lock_lines[0][1],
            "fragment_b": lock_lines[1][1],
        }
    return None


def _serialize_conflict(row) -> dict:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "title": row["title"],
        "source_file_names": row["source_file_names"],
        "fragment_a": row["fragment_a"],
        "fragment_b": row["fragment_b"],
        "resolution": row["resolution"],
        "resolution_type": row["resolution_type"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
```

- [ ] **Step 5: Add conflict list and resolve services**

Add:

```python
def list_document_conflicts(project_id: str, document_id: str, actor) -> list[dict]:
    _ = actor
    with connect() as db:
        if not document_repo.find_by_project_and_id(db, project_id, document_id):
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        return [_serialize_conflict(row) for row in document_repo.list_conflicts(db, document_id, status="open")]


def resolve_document_conflict(project_id: str, document_id: str, conflict_id: str, *, resolution: str, resolution_type: str, actor) -> dict:
    _ = actor
    with connect() as db:
        if not document_repo.find_by_project_and_id(db, project_id, document_id):
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        document_repo.resolve_conflict(db, conflict_id, resolution.strip(), resolution_type)
        rows = document_repo.list_conflicts(db, document_id, status="open")
        return {"success": True, "has_open_conflicts": len(rows) > 0}
```

- [ ] **Step 6: Add routes**

Add to `requirements.py`:

```python
@router.post("/{document_id}/merge")
def merge_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.merge_document_markdown(project_id, document_id, actor)


@router.get("/{document_id}/conflicts")
def list_requirement_conflicts(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_service.list_document_conflicts(project_id, document_id, actor)


@router.put("/{document_id}/conflicts/{conflict_id}")
def resolve_requirement_conflict(
    project_id: str,
    document_id: str,
    conflict_id: str,
    payload: ConflictResolutionIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.resolve_document_conflict(
        project_id,
        document_id,
        conflict_id,
        resolution=payload.resolution,
        resolution_type=payload.resolution_type,
        actor=actor,
    )
```

Update import:

```python
from app.schemas.document import ConflictResolutionIn, SourceDocumentUpdateIn, SourceMarkdownUpdateIn
```

- [ ] **Step 7: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: merge success and conflict tests pass.

- [ ] **Step 8: Commit**

```powershell
git add apps/backend/app/schemas/document.py apps/backend/app/services/document_service.py apps/backend/app/api/v1/requirements.py apps/backend/tests/test_document_service.py
git commit -m "feat: merge requirement standard markdown"
```

---

## Task 6: Add Frontend File Switcher

**Files:**
- Create: `apps/frontend/src/components/ai-testing/requirement-file-switcher.tsx`

- [ ] **Step 1: Create component**

Create:

```tsx
"use client";

import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type RequirementSwitcherFile = {
  id: string;
  original_filename: string;
  file_format: string;
  conversion_status: string;
  mapping_status: string;
  created_at: string;
};

type RequirementFileSwitcherProps = {
  files: RequirementSwitcherFile[];
  selectedFileId: string;
  onSelect: (fileId: string) => void;
  statusLabel: (status: string) => string;
};

export function RequirementFileSwitcher({ files, selectedFileId, onSelect, statusLabel }: RequirementFileSwitcherProps) {
  if (files.length === 0) {
    return <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground text-sm">暂无文件</div>;
  }

  return (
    <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
      {files.map((file) => (
        <Button
          key={file.id}
          type="button"
          variant="outline"
          className={cn("h-auto justify-start gap-3 p-3 text-left", selectedFileId === file.id && "border-primary bg-primary/5")}
          onClick={() => onSelect(file.id)}
        >
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium text-sm">{file.original_filename}</span>
            <span className="mt-1 flex flex-wrap gap-1">
              <Badge variant="secondary">{file.file_format.toUpperCase()}</Badge>
              <Badge variant={file.conversion_status === "failed" ? "destructive" : "outline"}>{statusLabel(file.conversion_status)}</Badge>
            </span>
          </span>
        </Button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Run frontend lint**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run lint
```

Expected: no lint errors from the new component.

- [ ] **Step 3: Commit**

```powershell
git add apps/frontend/src/components/ai-testing/requirement-file-switcher.tsx
git commit -m "feat: add requirement file switcher"
```

---

## Task 7: Rebuild Requirement Overview Page

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`

- [ ] **Step 1: Replace page state types**

Replace the old `DocumentDetailResponse`, `SourceFile`, and `PreviewState` driven shape with:

```tsx
type RequirementConflict = {
  id: string;
  title: string;
  source_file_names: string;
  fragment_a: string;
  fragment_b: string;
  resolution: string;
  resolution_type: string;
  status: string;
};

type SourceFile = {
  id: string;
  original_filename: string;
  file_format: string;
  created_at: string;
  conversion_status: string;
  mapping_status: string;
  version_id: string | null;
  version_no: number | null;
  markdown_file_path: string | null;
  conversion_summary: string;
  standard_file_status?: string;
  conflict_status?: string;
};

type RequirementOverviewResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    document_type: string;
    status: string;
    updated_at: string;
    current_version_id: string | null;
  };
  stats: {
    total_files: number;
    conversion_success: number;
    conversion_warning: number;
    conversion_failed: number;
    mergeable_files: number;
    open_conflicts: number;
    initial_requirement_status: string;
  };
  files: SourceFile[];
  has_open_conflicts: boolean;
  initial_markdown_content: string;
};
```

- [ ] **Step 2: Load overview instead of old detail/files split**

Use:

```tsx
const data = await apiRequest<RequirementOverviewResponse>(`/projects/${projectId}/requirements/${documentId}/overview`);
```

Keep one `overview` state and one `loading` state. Remove the separate `versions` table and `filesLoading`.

- [ ] **Step 3: Add tab state**

Use controlled tabs:

```tsx
const [activeTab, setActiveTab] = useState("overview");
const [selectedFileId, setSelectedFileId] = useState("");
```

Initialize `selectedFileId` to the first file id when overview loads.

- [ ] **Step 4: Add overview tab**

Render:

- Four stat blocks: 原始文件、可合并、待处理冲突、初始需求.
- Table with file name, format, conversion status, standard file status, mapping status, conflict status.
- Clickable file buttons switch tab and selected file.

Use existing `Table`, `Badge`, and `ShellSection`.

- [ ] **Step 5: Add original file tab**

Use `RequirementFileSwitcher`.

When selected file changes, call:

```tsx
apiRequest<{ original_filename: string; file_format: string; content_type: "text" | "download"; content?: string; download_path?: string }>(`/requirement-files/${selectedFile.id}/original`);
```

Render text content in `<pre>`. For download content, render a bordered information block with the path returned by backend. For pdf, use the same block unless backend later returns embeddable content.

- [ ] **Step 6: Add standard file tab with inline editing**

When selected file changes, call:

```tsx
apiRequest<{ original_filename: string; markdown_content: string; conversion_summary: string }>(`/requirement-files/${selectedFile.id}/markdown`);
```

Preview mode:

- Show `MarkdownPreview`.
- Buttons: `修改`, `合并`.

Edit mode:

- Replace preview with `Textarea`.
- Buttons: `保存`, `取消`.

Save:

```tsx
await apiRequest(`/requirement-files/${selectedFile.id}/markdown`, {
  method: "PUT",
  body: JSON.stringify({ markdown_content: markdownDraft, change_summary: "人工修订标准文件" }),
});
```

Toast: `标准文件已保存`.

- [ ] **Step 7: Add merge action**

Call:

```tsx
const result = await apiRequest<MergeResponse>(`/projects/${projectId}/requirements/${documentId}/merge`, { method: "POST" });
```

If `result.status === "merged"`:

- Toast `初始需求已生成`.
- Reload overview.
- Switch to `initial`.

If `result.status === "conflict"`:

- Store conflicts.
- Reload overview.
- Switch to `conflicts`.

- [ ] **Step 8: Add initial requirement tab**

Render:

```tsx
<MarkdownPreview
  className="requirement-document-preview"
  content={overview.initial_markdown_content}
  emptyText="尚未生成初始需求，请先在标准文件中发起合并。"
  indentParagraphs
/>
```

- [ ] **Step 9: Add conditional conflict tab**

Render the trigger only when `overview.has_open_conflicts` is true or local conflicts length is greater than zero.

Each conflict shows:

- title
- source file names
- fragment A
- fragment B
- textarea for resolution
- save button

Save calls:

```tsx
await apiRequest(`/projects/${projectId}/requirements/${documentId}/conflicts/${conflict.id}`, {
  method: "PUT",
  body: JSON.stringify({ resolution, resolution_type: "manual" }),
});
```

After all conflicts are resolved, reload overview. The tab hides when `has_open_conflicts` becomes false.

- [ ] **Step 10: Remove in-page version records**

Delete imports and JSX that exist only for the old version record Tab or edit-current-version dialog:

- `Dialog`
- `DialogContent`
- `DialogDescription`
- `DialogFooter`
- `DialogHeader`
- `DialogTitle`
- `Input`
- `Label`
- old `openEditDialog`
- old `handleSave`
- old `versions` rendering

Keep route-level version page untouched.

- [ ] **Step 11: Run frontend lint**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run lint
```

Expected: no lint errors.

- [ ] **Step 12: Commit**

```powershell
git add apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx
git commit -m "feat: build requirement overview workflow"
```

---

## Task 8: Full Verification

**Files:**
- No source edits unless verification finds a bug.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m unittest tests.test_document_service
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend lint**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run lint
```

Expected: no lint errors.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run build
```

Expected: build completes.

- [ ] **Step 4: Start backend**

Run:

```powershell
cd D:\project\test_project\apps\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Expected: backend responds on `http://127.0.0.1:8000`.

- [ ] **Step 5: Start frontend**

Run:

```powershell
cd D:\project\test_project\apps\frontend
npm run dev
```

Expected: frontend responds on `http://localhost:3000`.

- [ ] **Step 6: Browser verify**

Open:

```text
http://localhost:3000/projects/project-e6c870c3b9ac9634/requirements/doc-a17c5c2ebe7e25ce
```

Verify:

- Page title is `需求概览`.
- Tabs are `概览 / 原始文件 / 标准文件 / 初始需求`.
- No in-page `版本记录` tab exists.
- Original file tab can select a file.
- Standard file tab can show Markdown.
- `修改` switches preview area into editor.
- `保存` updates the standard file and does not create a visible version record on this page.
- `合并` either generates initial requirement or shows conflict tab.
- Conflict tab hides after conflicts are resolved and merge succeeds.

- [ ] **Step 7: Final commit if verification fixes were needed**

If changes were made during verification:

```powershell
git add <changed-files>
git commit -m "fix: verify requirement overview workflow"
```
