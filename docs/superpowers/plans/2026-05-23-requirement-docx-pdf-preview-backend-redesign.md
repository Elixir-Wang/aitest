# Requirement DOCX PDF Preview Backend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current ad-hoc DOCX preview logic with a backend-owned preview pipeline that stores generated PDFs under `preview/`, exposes explicit preview status, and removes silent local-environment dependency from business logic.

**Architecture:** Keep raw uploads, Markdown conversion, and PDF preview as separate file assets under the requirement directory. Markdown remains `DOCX -> Markdown`; preview remains `DOCX -> PDF`; the two outputs never depend on each other. A small preview service boundary owns preview status and provider selection, so the app can later switch from disabled/local/mock to LibreOffice, OnlyOffice, or a remote converter without changing frontend workflows.

**Tech Stack:** FastAPI, SQLite, existing `document_service`, existing file storage under `apps/backend/data/projects`, Next.js frontend PDF preview component.

---

## File Structure

- Modify: `apps/backend/app/seed/init_db.py`
  - Add `preview_status` and `preview_summary` to `source_document_file_mappings`.
  - Keep `preview_file_path`.
- Modify: `apps/backend/app/repositories/document_repo.py`
  - Accept and update preview fields through repository functions.
- Modify: `apps/backend/app/services/document_service.py`
  - Remove direct `_convert_to_pdf_preview()` local command lookup from upload flow.
  - Add explicit preview asset creation/status flow.
  - Return preview metadata from original-file APIs.
- Create: `apps/backend/app/services/document_preview_service.py`
  - Own preview provider behavior and generated PDF path convention.
- Modify: `apps/backend/app/api/v1/requirements.py`
  - Add `/requirement-files/{mapping_id}/preview/content`.
  - Keep `/original/content` for raw download only.
- Modify: `apps/backend/tests/test_document_service.py`
  - Replace the current “hidden local conversion” tests with explicit preview-status tests.
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
  - Read preview metadata and request preview content only when `preview_status = success`.
- Modify: `apps/frontend/src/components/ai-testing/original-file-preview.tsx`
  - Render PDF only when backend returns PDF preview.
  - Show precise status/failure text for DOCX without preview.

## Storage Convention

Use this directory layout:

```text
data/projects/{project_id}/requirements/{document_id}/
  raw/
    {mapping_id}-{original_filename}.docx
  preview/
    {mapping_id}.pdf
  markdown/
    conversions/
      {mapping_id}.md
      {mapping_id}_assets/
    versions/
      v1.md
      v2.md
```

Rules:

- `raw/` contains only user-uploaded files.
- `preview/` contains system-generated read-only preview PDFs.
- `markdown/conversions/` contains one Markdown standard file per source file.
- Deleting one source file deletes all assets that share the same `mapping_id`.

## Task 1: Add Preview Status To The Data Model

**Files:**
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write the failing schema test**

Add this assertion to `test_conflict_table_exists_in_isolated_store` or a new schema test:

```python
def test_file_mapping_has_preview_status_columns(self):
    with isolated_document_store():
        with connect() as db:
            rows = db.execute("PRAGMA table_info(source_document_file_mappings)").fetchall()

    columns = {row["name"] for row in rows}
    self.assertIn("preview_file_path", columns)
    self.assertIn("preview_status", columns)
    self.assertIn("preview_summary", columns)
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py -k preview_status_columns
```

Expected: FAIL because `preview_status` and `preview_summary` do not exist.

- [ ] **Step 3: Update schema and isolated test schema**

In `apps/backend/app/seed/init_db.py`, add:

```sql
preview_file_path TEXT,
preview_status TEXT NOT NULL DEFAULT 'unsupported',
preview_summary TEXT NOT NULL DEFAULT '',
```

In `_migrate_file_mappings()`, add:

```python
_ensure_column(db, "source_document_file_mappings", "preview_file_path", "TEXT")
_ensure_column(db, "source_document_file_mappings", "preview_status", "TEXT NOT NULL DEFAULT 'unsupported'")
_ensure_column(db, "source_document_file_mappings", "preview_summary", "TEXT NOT NULL DEFAULT ''")
```

Update the isolated test table in `apps/backend/tests/test_document_service.py` with the same three columns.

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py -k preview_status_columns
```

Expected: PASS.

## Task 2: Replace Silent Preview Generation With Explicit Preview Service Boundary

**Files:**
- Create: `apps/backend/app/services/document_preview_service.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write the failing upload behavior test**

Replace the current test that patches `_convert_to_pdf_preview` with:

```python
async def test_upload_docx_marks_preview_unsupported_when_provider_disabled(self):
    with isolated_document_store() as actor:
        with patch("app.services.document_service._convert_to_markdown", return_value=("# DOCX Markdown", "DOCX 转 Markdown")):
            result = await document_service.upload_documents(
                "project-1",
                [make_upload_file("原始需求.docx", b"docx-bytes")],
                actor,
                mode="new",
                document_name="原始需求",
            )

    file = result["files"][0]
    self.assertEqual(file["conversion_status"], "success")
    self.assertTrue(file["markdown_file_path"].endswith(".md"))
    self.assertIsNone(file["preview_file_path"])
    self.assertEqual(file["preview_status"], "unsupported")
    self.assertIn("未启用", file["preview_summary"])
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py -k provider_disabled
```

Expected: FAIL because preview status is not serialized yet.

- [ ] **Step 3: Create `document_preview_service.py`**

Create:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PREVIEW_UNSUPPORTED_STATUS = "unsupported"
PREVIEW_SUCCESS_STATUS = "success"
PREVIEW_FAILED_STATUS = "failed"


@dataclass(frozen=True)
class PreviewResult:
    file_path: str | None
    status: str
    summary: str


def generate_preview_pdf(
    *,
    filename: str,
    file_format: str,
    raw_bytes: bytes,
    preview_path: Path,
) -> PreviewResult:
    _ = filename
    _ = raw_bytes
    if file_format not in {"doc", "docx"}:
        return PreviewResult(None, PREVIEW_UNSUPPORTED_STATUS, "该文件格式不需要生成 PDF 原样预览。")

    return PreviewResult(None, PREVIEW_UNSUPPORTED_STATUS, "后端未启用 DOCX 原样预览转换服务。")
```

- [ ] **Step 4: Use preview service from upload flow**

In `document_service.py`, remove:

```python
import subprocess
import tempfile
```

Delete the whole `_convert_to_pdf_preview()` function.

Import:

```python
from app.services.document_preview_service import generate_preview_pdf
```

In `_save_source_file()`, after Markdown conversion, call:

```python
preview_result = generate_preview_pdf(
    filename=safe_filename,
    file_format=file_format,
    raw_bytes=raw_bytes,
    preview_path=preview_path,
)
```

Pass these to `document_repo.create_file_mapping()`:

```python
preview_file_path=preview_result.file_path,
preview_status=preview_result.status,
preview_summary=preview_result.summary,
```

- [ ] **Step 5: Run the test and verify it passes**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py -k provider_disabled
```

Expected: PASS.

## Task 3: Repository And Serialization Support For Preview Fields

**Files:**
- Modify: `apps/backend/app/repositories/document_repo.py`
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Extend repository insert signature**

In `create_file_mapping()`, add optional parameters:

```python
preview_file_path: str | None = None,
preview_status: str = "unsupported",
preview_summary: str = "",
```

Insert the columns:

```sql
preview_file_path, preview_status, preview_summary
```

- [ ] **Step 2: Extend `serialize_file_mapping()`**

Return:

```python
"preview_file_path": row["preview_file_path"] if "preview_file_path" in row.keys() else None,
"preview_status": row["preview_status"] if "preview_status" in row.keys() else "unsupported",
"preview_summary": row["preview_summary"] if "preview_summary" in row.keys() else "",
```

- [ ] **Step 3: Run document tests**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py
```

Expected: PASS.

## Task 4: Separate Raw Download From Preview Content

**Files:**
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Write failing service tests**

Add:

```python
def test_get_original_file_returns_raw_docx_and_preview_metadata(self):
    with isolated_document_store() as actor:
        document_dir = Path(document_service.project_requirement_dir("project-1", "doc-1"))
        source_path = document_dir / "raw" / "docmap-1-raw.docx"
        preview_path = document_dir / "preview" / "docmap-1.pdf"
        source_path.parent.mkdir(parents=True)
        preview_path.parent.mkdir(parents=True)
        source_path.write_bytes(b"docx")
        preview_path.write_bytes(b"%PDF-1.4")
        with connect() as db:
            db.execute("""
                INSERT INTO source_documents
                  (id, project_id, name, document_type, current_version_id, status, created_by)
                VALUES
                  ('doc-1', 'project-1', '登录需求', 'PRD', NULL, 'pending_merge', 'u-admin')
            """)
            document_repo.create_file_mapping(
                db,
                mapping_id="docmap-1",
                document_id="doc-1",
                version_id=None,
                source_file_path=str(source_path),
                original_filename="raw.docx",
                file_format="docx",
                markdown_file_path=None,
                conversion_status="failed",
                mapping_status="pending_merge",
                conversion_summary="失败",
                created_by="u-admin",
                preview_file_path=str(preview_path),
                preview_status="success",
                preview_summary="PDF 预览已生成。",
            )

    result = document_service.get_original_file("docmap-1")
    self.assertEqual(result["content_type"], "download")
    self.assertEqual(result["download_path"], str(source_path))
    self.assertEqual(result["preview_status"], "success")
    self.assertEqual(result["preview_content_type"], "pdf")
    self.assertEqual(result["preview_path"], str(preview_path))
```

- [ ] **Step 2: Implement service response**

For binary original files, return raw download path and preview metadata separately:

```python
return {
    "id": row["id"],
    "original_filename": row["original_filename"],
    "file_format": row["file_format"],
    "content_type": "download",
    "download_path": str(path),
    "preview_status": row["preview_status"],
    "preview_summary": row["preview_summary"],
    "preview_content_type": "pdf" if row["preview_status"] == "success" else None,
    "preview_path": row["preview_file_path"] if row["preview_status"] == "success" else None,
}
```

- [ ] **Step 3: Add preview content endpoint**

In `requirements.py`, add:

```python
@file_router.get("/{mapping_id}/preview/content")
def get_requirement_preview_content(mapping_id: str, actor=Depends(current_user)) -> FileResponse:
    _ = actor
    preview = document_service.get_preview_file(mapping_id)
    return FileResponse(Path(preview["preview_path"]), media_type="application/pdf", filename=preview["preview_filename"])
```

In `document_service.py`, add:

```python
def get_preview_file(mapping_id: str) -> dict:
    with connect() as db:
        row = document_repo.find_file_mapping(db, mapping_id)
        if not row:
            raise api_error(404, "DOCUMENT_FILE_NOT_FOUND", "来源文件不存在。")
        if row["preview_status"] != "success" or not row["preview_file_path"]:
            raise api_error(409, "DOCUMENT_PREVIEW_NOT_READY", row["preview_summary"] or "原样预览尚未生成。")
        preview_path = Path(row["preview_file_path"])
        if not preview_path.exists():
            raise api_error(404, "DOCUMENT_PREVIEW_MISSING", "原样预览文件不存在。")
        return {
            "preview_path": str(preview_path),
            "preview_filename": f"{Path(row['original_filename']).stem}.pdf",
        }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py
```

Expected: PASS.

## Task 5: Update Delete To Clean All Mapping Assets

**Files:**
- Modify: `apps/backend/app/services/document_service.py`
- Modify: `apps/backend/tests/test_document_service.py`

- [ ] **Step 1: Keep and extend delete test**

Ensure `test_delete_source_file_removes_converted_assets` asserts:

```python
self.assertFalse(source_path.exists())
self.assertFalse(preview_path.exists())
self.assertFalse(markdown_path.exists())
self.assertFalse(assets_dir.exists())
```

- [ ] **Step 2: Implement cleanup**

In `delete_source_file()`, compute paths before deleting DB row:

```python
source_path = row["source_file_path"]
markdown_path_value = row["markdown_file_path"]
preview_path_value = row["preview_file_path"]
assets_dir = _converted_assets_dir(row, markdown_path_value)
```

Then unlink all existing assets.

- [ ] **Step 3: Run delete test**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests/test_document_service.py -k delete_source_file
```

Expected: PASS.

## Task 6: Update Frontend Original File Preview Flow

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
- Modify: `apps/frontend/src/components/ai-testing/original-file-preview.tsx`

- [ ] **Step 1: Update frontend response type**

In `page.tsx`, change original file API type to include:

```ts
preview_status: "pending" | "processing" | "success" | "failed" | "unsupported";
preview_summary: string;
preview_content_type?: "pdf" | null;
preview_path?: string | null;
```

- [ ] **Step 2: Load preview content only when successful**

Replace the current direct original blob load with:

```ts
if (data.preview_status === "success" && data.preview_content_type === "pdf") {
  const blob = await apiBlobRequest(`/requirement-files/${file.id}/preview/content`);
  setOriginalPreview({
    title: data.original_filename,
    fileFormat: "pdf",
    contentType: "file",
    content: data.preview_path ?? "",
    objectUrl: URL.createObjectURL(blob),
    previewStatus: data.preview_status,
    previewSummary: data.preview_summary,
  });
  return;
}

setOriginalPreview({
  title: data.original_filename,
  fileFormat: data.file_format,
  contentType: "file",
  content: "",
  previewStatus: data.preview_status,
  previewSummary: data.preview_summary,
});
```

- [ ] **Step 3: Show precise status in `OriginalFilePreview`**

Extend `OriginalPreview`:

```ts
previewStatus?: "pending" | "processing" | "success" | "failed" | "unsupported";
previewSummary?: string;
```

For DOC/DOCX without PDF object URL, show:

```tsx
<div className="text-muted-foreground">{preview.previewSummary || "原样预览尚未生成。"}</div>
```

- [ ] **Step 4: Run frontend checks**

Run:

```powershell
cd apps/frontend
npm run lint
npm run build
```

Expected: both PASS.

## Task 7: Final Verification

**Files:**
- All touched files.

- [ ] **Step 1: Backend test suite**

Run:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m pytest apps/backend/tests
```

Expected: all tests pass.

- [ ] **Step 2: Frontend checks**

Run:

```powershell
cd apps/frontend
npm run lint
npm run build
```

Expected: both pass.

- [ ] **Step 3: Manual browser verification**

Start services if needed, then open:

```text
http://localhost:3000/projects/{project_id}/requirements/{document_id}?tab=original
```

Verify:

- Existing DOCX without preview says “后端未启用 DOCX 原样预览转换服务。” or equivalent precise message.
- PDF source files still render in PDF preview.
- TXT/MD still show text preview.
- Deleting a source file removes raw, preview, Markdown, and assets.

## Self-Review

- The plan removes the bad `_convert_to_pdf_preview()` local command lookup from business upload flow.
- The plan keeps `preview/` as the correct storage location for generated PDFs.
- The plan keeps Markdown conversion independent from PDF preview generation.
- The plan avoids frontend DOCX HTML/mammoth fallback as “原样预览”.
- The plan adds status and summary so failures are visible instead of silently becoming “不支持预览”.
