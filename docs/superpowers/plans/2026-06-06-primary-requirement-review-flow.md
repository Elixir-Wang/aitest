# Primary Requirement Review Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "set as primary requirement" only select the main source file, and move requirement review / final requirement generation to an explicit button on the primary file's standard Markdown page.

**Architecture:** Split the current implicit chain into two explicit backend actions: primary-file selection and requirement-review generation. The primary-file endpoint only updates `source_document_file_mappings.file_role`; a new review endpoint reads the primary file's standard Markdown, creates a `source_document_versions` row, updates `source_documents.current_version_id`, and then runs requirement analysis against that version.

**Tech Stack:** FastAPI backend, SQLite repositories under `apps/backend/app/repositories`, document services under `apps/backend/app/services/document`, pytest backend tests, Next.js/React frontend, Biome lint.

---

## File Structure

- Modify `apps/backend/app/services/document/service.py`
  - Change `set_primary_requirement_file` so it does not create a version or update `current_version_id`.
  - Add `review_primary_requirement_file`, which explicitly generates the current/final requirement version from the primary file standard Markdown and runs requirement analysis.
  - Update analysis-empty wording from "生成初始需求" to "先完成需求评审".

- Modify `apps/backend/app/api/v1/requirements.py`
  - Keep `PUT /projects/{project_id}/requirements/{document_id}/files/{mapping_id}/primary`.
  - Add `POST /projects/{project_id}/requirements/{document_id}/review`.

- Modify `apps/backend/app/repositories/document_repo.py`
  - Reuse existing `find_primary_file_mapping`, `set_primary_file_mapping`, `create_version`, `link_file_mapping_to_version`, and `update_current_version`.
  - Add no new tables unless implementation discovers no existing helper can fetch the primary file with Markdown path.

- Modify `apps/backend/tests/test_requirement_primary_file_service.py`
  - Replace tests that assert primary selection creates versions.
  - Add tests for primary selection only changing roles.
  - Add tests for explicit review creating/updating the final requirement version.

- Modify `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`
  - Update `setPrimaryFile` toast and behavior.
  - Add "需求评审" button in the standard-file tab only when selected file is primary and standard Markdown is ready.
  - Hide the `需求澄清` tab before review finishes; show it only when the latest review returns clarification questions.
  - Remove "需求分析" actions from "需求澄清" and "最终需求" if they imply analysis can be run before review.
  - Update disabled copy / empty text away from "初始需求".

- Modify `apps/frontend/src/lib/api-client.ts` only if this repo has typed endpoint wrappers for requirement operations. If the page calls `apiRequest` directly, do not touch this file.

---

## Behavior Contract

1. `设为主需求`
   - Validates the file belongs to the document and standard Markdown exists.
   - Updates file roles: selected file becomes `primary`; previous primary becomes `supporting`.
   - Does not create a `source_document_versions` row.
   - Does not update `source_documents.current_version_id`.
   - Does not run requirement analysis.
   - Frontend stays on the current tab or opens the selected file's standard-file tab.
   - Toast: `已设为主需求文件`.

2. `需求评审`
   - Only available on the standard-file tab when the selected file is `primary`.
   - Reads the primary file's `markdown_file_path`.
   - Creates a new `source_document_versions` row using that Markdown.
   - Updates `source_documents.current_version_id`.
   - Links the primary file mapping to the generated version.
   - Runs requirement analysis against that new version.
   - Returns the same analysis payload shape currently returned by `/analysis`.
   - Frontend stores `analysisResult`, refreshes overview, then shows `需求澄清` only if there are clarification questions.
   - If the review returns no clarification questions, frontend does not show the `需求澄清` tab and directly enters `最终需求`.
   - Before any successful review result exists, the `需求澄清` tab is hidden.

3. Existing final requirement content
   - This plan does not add the "clear final requirement on primary switch" behavior, because the new design says primary switch should not rewrite final requirement.
   - If product later wants stale-content warning, add a non-blocking banner: `主需求文件已切换，当前最终需求可能不是基于最新主需求评审生成。`

---

### Task 1: Backend Tests For Primary Selection Without Version Generation

**Files:**
- Modify: `apps/backend/tests/test_requirement_primary_file_service.py`

- [ ] **Step 1: Replace the primary-upload test expectation**

Change the current test named `test_primary_upload_generates_current_requirement_version` to assert that conversion marks the first file primary but does not create a current version.

```python
@pytest.mark.anyio
async def test_primary_upload_marks_first_file_without_generating_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n主需求内容。\n", "已生成标准 Markdown。"

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]

    await document_service.convert_pending_file_mappings([mapping_id])

    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)
    assert overview["document"]["current_version_id"] is None
    assert overview["files"][0]["file_role"] == "primary"
    assert overview["files"][0]["version_no"] is None
    assert overview["initial_markdown_content"] == ""
```

- [ ] **Step 2: Replace the manual-primary test expectation**

Change the current test named `test_setting_supporting_file_as_primary_creates_new_version` to assert that switching primary only changes roles.

```python
@pytest.mark.anyio
async def test_setting_supporting_file_as_primary_only_changes_roles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n标准内容。\n", "已生成标准 Markdown。"

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main"), _upload_file("supplement.md", "# supplement")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_ids = [item["id"] for item in result["files"]]
    main_mapping_id = next(item["id"] for item in result["files"] if item["original_filename"] == "main.md")
    supplement_mapping_id = next(item["id"] for item in result["files"] if item["original_filename"] == "supplement.md")
    await document_service.convert_pending_file_mappings(mapping_ids)

    overview = document_service.set_primary_requirement_file(
        "project-1",
        result["document"]["id"],
        supplement_mapping_id,
        ACTOR,
    )

    roles = {item["id"]: item["file_role"] for item in overview["files"]}
    assert roles[supplement_mapping_id] == "primary"
    assert roles[main_mapping_id] == "supporting"
    assert overview["document"]["current_version_id"] is None
    assert overview["initial_markdown_content"] == ""
```

- [ ] **Step 3: Run the backend test to verify it fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py -q
```

Expected: FAIL because current implementation still creates versions during conversion / primary switch.

---

### Task 2: Backend Primary Selection Implementation

**Files:**
- Modify: `apps/backend/app/services/document/file_service.py`
- Modify: `apps/backend/app/services/document/service.py`

- [ ] **Step 1: Stop primary conversion from creating a current version**

In `apps/backend/app/services/document/file_service.py`, find the conversion success path that creates a version when `file_role == "primary"`. Remove the version creation and `update_current_version` call from that conversion path. Keep storing `markdown_file_path`, `conversion_status`, and `conversion_summary`.

The resulting conversion behavior should still leave the mapping as primary:

```python
document_repo.update_file_mapping_conversion(
    db,
    mapping_id,
    status=CONVERSION_SUCCESS_STATUS,
    markdown_file_path=store_path(markdown_path) or str(markdown_path),
    conversion_summary=summary,
)
```

- [ ] **Step 2: Simplify `set_primary_requirement_file`**

Replace the body after validation in `apps/backend/app/services/document/service.py` so it only updates file roles.

```python
        document_repo.set_primary_file_mapping(db, document_id, mapping_id)

    result = get_document_overview(project_id, document_id, actor)
    operation_log_service.record_change(
        log_type="audit",
        module="requirement",
        action="set_primary_file",
        object_type="source_file",
        object_id=mapping_id,
        object_name=file_mapping["original_filename"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"设置主需求文件：{file_mapping['original_filename']}",
        after={"file_role": "primary"},
    )
    return result
```

Keep the existing validations:

```python
if file_mapping["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"} or not file_mapping["markdown_file_path"]:
    raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成标准文件转换后再设为主需求。")
```

- [ ] **Step 3: Run the focused test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py -q
```

Expected: PASS for the two rewritten primary-selection tests.

---

### Task 3: Backend Explicit Requirement Review API

**Files:**
- Modify: `apps/backend/app/services/document/service.py`
- Modify: `apps/backend/app/api/v1/requirements.py`
- Modify: `apps/backend/tests/test_requirement_primary_file_service.py`

- [ ] **Step 1: Add failing test for explicit review**

Append this test to `apps/backend/tests/test_requirement_primary_file_service.py`.

```python
@pytest.mark.anyio
async def test_review_primary_requirement_file_generates_version_and_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    async def fake_convert_to_markdown(filename, raw_bytes=None, *, source_path=None, assets_dir=None):
        return f"# {filename}\n\n标准内容。\n", "已生成标准 Markdown。"

    class FakeQualityGate:
        result = "passed"
        testability_score = 90
        blocking_issues = []

    class FakeAnalysisOutput:
        status = "completed"
        analysis_summary = "需求评审完成。"
        quality_gate = FakeQualityGate()

        def model_dump(self):
            return {
                "status": "completed",
                "analysis_summary": "需求评审完成。",
                "modules": [],
                "clarification_questions": [],
                "quality_gate": {
                    "result": "passed",
                    "testability_score": 90,
                    "blocking_issues": [],
                    "warnings": [],
                },
                "traceability": [],
            }

    async def fake_run_requirement_analysis(input_data):
        assert "# main.md" in input_data.markdown_content
        return FakeAnalysisOutput()

    monkeypatch.setattr("app.services.document.file_service.convert_to_markdown", fake_convert_to_markdown)
    monkeypatch.setattr("app.services.document.service.run_requirement_analysis", fake_run_requirement_analysis)

    result = await document_service.upload_documents(
        "project-1",
        [_upload_file("main.md", "# main")],
        ACTOR,
        document_name="登录需求",
    )
    mapping_id = result["files"][0]["id"]
    await document_service.convert_pending_file_mappings([mapping_id])

    review = await document_service.review_primary_requirement_file("project-1", result["document"]["id"], ACTOR)
    overview = document_service.get_document_overview("project-1", result["document"]["id"], ACTOR)

    assert review["status"] == "completed"
    assert review["analysis_summary"] == "需求评审完成。"
    assert overview["document"]["current_version"]["version_no"] == 1
    assert "# main.md" in overview["initial_markdown_content"]
    assert overview["files"][0]["version_no"] == 1
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py::test_review_primary_requirement_file_generates_version_and_analysis -q
```

Expected: FAIL with `AttributeError` because `review_primary_requirement_file` does not exist.

- [ ] **Step 3: Add service method**

Add this function near `analyze_document_requirement` in `apps/backend/app/services/document/service.py`.

```python
async def review_primary_requirement_file(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")

        primary_file = document_repo.find_primary_file_mapping(db, document_id)
        if not primary_file:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_REQUIRED", "请先选择主需求文件后再进行需求评审。")
        if primary_file["conversion_status"] not in {CONVERSION_SUCCESS_STATUS, "warning"} or not primary_file["markdown_file_path"]:
            raise api_error(409, "DOCUMENT_PRIMARY_FILE_NOT_READY", "请先完成主需求标准文件转换后再进行需求评审。")

        markdown_path = resolve_stored_path(primary_file["markdown_file_path"]) or Path(primary_file["markdown_file_path"])
        if not markdown_path.exists():
            raise api_error(404, "DOCUMENT_MARKDOWN_MISSING", "主需求标准文件不存在。")

        markdown_content = markdown_path.read_text(encoding="utf-8")
        version_id = f"docver-{secrets.token_hex(8)}"
        version_no = document_repo.next_version_no(db, document_id)
        version_path = _version_markdown_path(project_id, document_id, version_no)
        version_path.parent.mkdir(parents=True, exist_ok=True)
        version_path.write_text(markdown_content, encoding="utf-8")

        document_repo.create_version(
            db,
            version_id=version_id,
            document_id=document_id,
            version_no=version_no,
            file_path=store_path(version_path) or str(version_path),
            source_action="requirement_review",
            change_summary=f"需求评审生成最终需求：{primary_file['original_filename']}",
            diff_summary="从主需求标准文件执行需求评审后生成最终需求版本。",
            created_by=actor["id"],
        )
        document_repo.link_file_mapping_to_version(db, primary_file["id"], version_id)
        document_repo.update_current_version(db, document_id, version_id, DOCUMENT_VERSIONED_STATUS)

    return await analyze_document_requirement(project_id, document_id, actor)
```

- [ ] **Step 4: Add API route**

In `apps/backend/app/api/v1/requirements.py`, add this route next to `/analysis`.

```python
@router.post("/{document_id}/review")
async def review_requirement(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return await document_service.review_primary_requirement_file(project_id, document_id, actor)
```

- [ ] **Step 5: Update no-version analysis message**

In `analyze_document_requirement`, change:

```python
raise api_error(409, "REQUIREMENT_ANALYSIS_NO_VERSION", "请先选择主需求文件生成初始需求后再分析。")
```

to:

```python
raise api_error(409, "REQUIREMENT_ANALYSIS_NO_VERSION", "请先在主需求标准文件中完成需求评审。")
```

- [ ] **Step 6: Run focused backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py -q
```

Expected: PASS.

---

### Task 4: Frontend Primary Selection UX

**Files:**
- Modify: `apps/frontend/src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx`

- [ ] **Step 1: Update primary-selection API handling**

Change `setPrimaryFile` so it does not imply version generation and does not jump to final.

```tsx
async function setPrimaryFile(file: SourceFile) {
  setSettingPrimaryFileId(file.id);
  try {
    await apiRequest(`/projects/${projectId}/requirements/${documentId}/files/${file.id}/primary`, {
      method: "PUT",
    });
    toast.success("已设为主需求文件");
    await loadOverview({ silent: true });
    selectFileForTab(file.id, "standard");
  } catch (requestError) {
    toast.error(requestError instanceof Error ? requestError.message : "主需求文件设置失败");
  } finally {
    setSettingPrimaryFileId("");
  }
}
```

- [ ] **Step 2: Add review loading state**

Near existing analysis state, add:

```tsx
const [reviewLoading, setReviewLoading] = useState(false);
```

- [ ] **Step 3: Add review handler**

Add this function near `runRequirementAnalysis`.

```tsx
async function reviewPrimaryRequirement() {
  if (!selectedFile || selectedFile.file_role !== "primary") {
    toast.error("请先选择主需求标准文件");
    return;
  }
  setReviewLoading(true);
  try {
    notifyAiTaskStarted();
    const result = await apiRequest<RequirementAnalysisResult>(
      `/projects/${projectId}/requirements/${documentId}/review`,
      { method: "POST" },
    );
    setAnalysisResult(result);
    toast.success("需求评审已完成");
    await loadOverview({ silent: true });
    setActiveTab(result.output.clarification_questions.length > 0 ? "clarification" : "final");
  } catch (requestError) {
    toast.error(requestError instanceof Error ? requestError.message : "需求评审失败");
  } finally {
    setReviewLoading(false);
  }
}
```

- [ ] **Step 4: Add clarification-tab visibility rules**

Add a derived flag near other render-time constants:

```tsx
const hasClarificationQuestions = Boolean(analysisResult?.output.clarification_questions.length);
```

Update query-tab initialization so a stale `?tab=clarification` URL does not open a hidden tab before review creates clarification questions:

```tsx
if (queryTab === "initial") {
  setActiveTab("final");
} else if (queryTab === "clarification") {
  setActiveTab(hasClarificationQuestions ? "clarification" : "final");
} else if (queryTab && ["overview", "original", "standard", "final"].includes(queryTab)) {
  setActiveTab(queryTab);
}
```

The effect dependencies must include `hasClarificationQuestions` if this logic lives in an effect.

Render the `需求澄清` tab trigger only when review found clarification questions:

```tsx
{hasClarificationQuestions ? <TabsTrigger value="clarification">需求澄清</TabsTrigger> : null}
```

Wrap the `TabsContent value="clarification"` block with the same condition:

```tsx
{hasClarificationQuestions ? (
  <TabsContent value="clarification">
    {/* existing clarification result view */}
  </TabsContent>
) : null}
```

- [ ] **Step 5: Replace the standard-file primary button**

In the standard-file tab action area, replace the current primary button behavior with:

```tsx
{selectedFile?.file_role === "primary" ? (
  <Button
    disabled={
      reviewLoading ||
      !selectedFile ||
      !["success", "warning"].includes(selectedFile.conversion_status)
    }
    onClick={reviewPrimaryRequirement}
    type="button"
  >
    {reviewLoading ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
    {reviewLoading ? "评审中" : "需求评审"}
  </Button>
) : (
  <Button
    disabled={
      !selectedFile ||
      settingPrimaryFileId === selectedFile.id ||
      !["success", "warning"].includes(selectedFile.conversion_status)
    }
    onClick={() => selectedFile && setPrimaryFile(selectedFile)}
    type="button"
  >
    {settingPrimaryFileId === selectedFile?.id ? (
      <Loader2 className="size-4 animate-spin" />
    ) : (
      <Check className="size-4" />
    )}
    设为主需求
  </Button>
)}
```

- [ ] **Step 6: Remove review actions from result tabs**

Remove the "需求分析/重新分析" buttons from `需求澄清` and `最终需求`. Requirement review must be triggered from the primary file's `标准文件` tab so the user always sees which standard Markdown is being reviewed.

Keep these tabs as result views:

- `需求澄清`: appears only after review returns one or more clarification questions, and displays those questions.
- `最终需求`: appears normally and displays the latest generated final requirement content.

- [ ] **Step 7: Update user-visible copy**

Change these visible strings:

```tsx
description="查看原始文件、标准文件、主需求和评审结果。"
```

```tsx
emptyText="尚未生成最终需求，请先在主需求标准文件中执行需求评审。"
```

```tsx
{analysisResult ? "暂无待澄清问题。" : "尚未执行需求评审，完成评审后会在这里展示澄清问题。"}
```

- [ ] **Step 8: Run frontend lint**

Run:

```powershell
cd apps/frontend
npm run lint -- "src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx"
```

Expected: PASS.

---

### Task 5: Integration Verification

**Files:**
- Verify only; no planned code edits.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_requirement_primary_file_service.py tests/test_task_service.py tests/test_ai_agent_model_assignments.py -q
```

Expected: PASS.

- [ ] **Step 2: Compile backend**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Expected: command exits with code 0.

- [ ] **Step 3: Run frontend lint for touched files**

Run:

```powershell
cd apps/frontend
npm run lint -- "src/app/(main)/projects/[projectId]/requirements/[documentId]/page.tsx" "src/lib/api-client.ts"
```

Expected: PASS. If `src/lib/api-client.ts` was not modified, linting it is still acceptable.

- [ ] **Step 4: Manual browser smoke test**

Start the normal backend/frontend services if they are not already running. In the requirement detail page:

1. Upload or use a requirement with multiple source files.
2. Click `设为主需求` on a supporting file.
3. Confirm the row role changes to `主需求`.
4. Confirm final requirement content does not change immediately.
5. Open that file's `标准文件` tab.
6. Confirm the primary file shows `需求评审`.
7. Click `需求评审`.
8. If review returns clarification questions, confirm `需求澄清` tab appears and the page enters `需求澄清`.
9. If review returns no clarification questions, confirm `需求澄清` tab stays hidden and the page enters `最终需求`.
10. Confirm final requirement content is generated only after `需求评审`, not after `设为主需求`.

---

## Self-Review

- Spec coverage: The plan covers the user's revised product design: primary switch only selects input; review moves to primary standard file; final requirement generation becomes explicit.
- Placeholder scan: No `TBD`, `TODO`, or unspecified "handle later" steps remain.
- Type consistency: Backend service method is consistently named `review_primary_requirement_file`; frontend handler is `reviewPrimaryRequirement`; API route is `POST /review`.
