# Knowledge Chat Project Scope Switcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unused knowledge chat input controls with a project scope switcher that follows the top-right project context and can query all active projects when allowed.

**Architecture:** Keep current single-project knowledge chat behavior intact. Add an explicit all-project query path instead of silently falling back to the first active project. The frontend computes an effective query scope from the global project context and the input-level selection.

**Tech Stack:** Next.js React frontend, Zustand project context store, FastAPI backend, Pydantic schemas, SQLite repositories, existing knowledge chat services and node/python tests.

---

## File Structure

- Modify `apps/backend/app/schemas/knowledge.py`
  - Add optional project identity fields to `KnowledgeSourceRef`-compatible API output if the agent schema is extended.
- Modify `apps/backend/app/agents/knowledge_chat/schemas.py`
  - Add project identity to source inputs or refs so all-project answers can attribute facts.
- Modify `apps/backend/app/services/knowledge/service.py`
  - Keep current project-scoped query functions.
  - Add all-project stream query service.
  - Reuse project source collection rules.
- Modify `apps/backend/app/api/v1/knowledge.py`
  - Keep `/projects/{project_id}/knowledge/query/stream`.
  - Add `POST /knowledge/query/stream`.
- Modify `apps/frontend/src/lib/api-client.ts`
  - Add `project_id` and `project_name` to `ApiKnowledgeSourceRef` if backend returns them.
- Modify `apps/frontend/src/components/ui/knowledge-chat-input.tsx`
  - Remove `Clock` and unused thinking state.
  - Replace `+` button with project scope selector props.
  - Collapse model label to model name only.
- Modify `apps/frontend/src/app/(main)/knowledge/page.tsx`
  - Track input-level scope.
  - Derive effective query endpoint.
  - Reset chat state when effective scope changes.
  - Render project-aware source refs.
- Test `apps/backend/tests/test_knowledge_conversations.py`
  - Add all-project query coverage while preserving current conversation tests.
- Test `apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs`
  - Extend source checks for project scope selector and removed clock.

## Implementation Tasks

### Task 1: Add Backend All-Project Query Contract

**Files:**
- Modify: `apps/backend/app/agents/knowledge_chat/schemas.py`
- Modify: `apps/backend/app/schemas/knowledge.py`
- Modify: `apps/backend/app/services/knowledge/service.py`
- Modify: `apps/backend/app/api/v1/knowledge.py`
- Test: `apps/backend/tests/test_knowledge_conversations.py`

- [ ] **Step 1: Inspect current dirty diffs**

Run:

```powershell
git diff -- apps/backend/app/agents/knowledge_chat/schemas.py apps/backend/app/schemas/knowledge.py apps/backend/app/services/knowledge/service.py apps/backend/app/api/v1/knowledge.py apps/backend/tests/test_knowledge_conversations.py
```

Expected: review existing local changes and preserve them. Do not revert unrelated edits.

- [ ] **Step 2: Write failing backend test**

Add this test to `apps/backend/tests/test_knowledge_conversations.py`:

```python
def test_all_project_knowledge_query_collects_active_project_sources(monkeypatch, tmp_path) -> None:
    from app.schemas.knowledge import KnowledgeQueryOutput
    from app.services.knowledge import service

    _use_temp_db(monkeypatch, tmp_path)
    _seed_project(monkeypatch, tmp_path)

    second_doc = tmp_path / "checkout.md"
    second_doc.write_text("# 结算\n用户可以提交订单并完成结算。", encoding="utf-8")
    archived_doc = tmp_path / "archived.md"
    archived_doc.write_text("# 归档\n归档项目不应该被全部项目检索。", encoding="utf-8")

    from app.core import db as core_db

    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-2', '订单项目', 'active', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-2', 'project-2', '订单需求', 'requirement', 'version-2', 'finalized', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, created_by)
            VALUES ('version-2', 'doc-2', 1, '', ?, 'upload', 'u-admin')
            """,
            (str(second_doc),),
        )
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-archived', '归档项目', 'archived', '', 'u-admin')
            """
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES ('doc-archived', 'project-archived', '归档需求', 'requirement', 'version-archived', 'finalized', 'u-admin')
            """
        )

    captured_project_names: list[str] = []

    async def fake_stream_knowledge_chat(input_data, search_project_knowledge):
        output = await search_project_knowledge(input_data.question)
        yield {"type": "message_delta", "delta": "done"}
        yield {"type": "metadata", "output": output}

    async def fake_run_knowledge_query(input_data):
        captured_project_names.extend(doc.project_name for doc in input_data.source_documents)
        return KnowledgeQueryOutput(
            answer="跨项目回答",
            source_refs=[
                service.KnowledgeSourceRef(
                    source_type="requirement",
                    source_id=doc.version_id,
                    source_title=doc.document_name,
                    location="最终需求文档",
                    excerpt=doc.project_name,
                    project_id=doc.project_id,
                    project_name=doc.project_name,
                )
                for doc in input_data.source_documents
            ],
            used_requirement_versions=[doc.version_id for doc in input_data.source_documents],
            used_exploration_runs=[],
            knowledge_queried=True,
        )

    monkeypatch.setattr(service.knowledge_chat_service, "stream_knowledge_chat", fake_stream_knowledge_chat)
    monkeypatch.setattr(service.knowledge_query_service, "run_knowledge_query", fake_run_knowledge_query)
    actor = {"id": "u-admin", "username": "admin", "nickname": "平台管理员", "role": "admin", "project_scope": "全部项目"}

    events = asyncio.run(
        _collect_async_events(
            service.stream_all_project_knowledge_query(
                actor,
                service.KnowledgeQueryRequest(question="查询全部项目", include_explorations=False),
            )
        )
    )

    metadata = next(event for event in events if event["type"] == "metadata")
    assert captured_project_names == ["测试项目", "订单项目"]
    assert [ref["project_name"] for ref in metadata["result"]["source_refs"]] == ["测试项目", "订单项目"]
    assert metadata["result"]["conversation"] is None
```

Also add this helper near the test helpers:

```python
async def _collect_async_events(iterator):
    return [event async for event in iterator]
```

Expected initially: FAIL because `stream_all_project_knowledge_query`, project identity fields, and all-project output shape do not exist.

- [ ] **Step 3: Run failing backend test**

Run from `apps/backend` using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge_conversations.py::test_all_project_knowledge_query_collects_active_project_sources -q
```

Expected: FAIL with missing service/schema attributes.

- [ ] **Step 4: Extend knowledge schemas**

In `apps/backend/app/agents/knowledge_chat/schemas.py`, update source document and ref models:

```python
class KnowledgeSourceDocumentInput(BaseModel):
    project_id: str
    project_name: str
    document_id: str
    document_name: str
    version_id: str
    version_no: int
    markdown_content: str
```

```python
class KnowledgeSourceRef(BaseModel):
    source_type: Literal["requirement", "exploration", "manual"]
    source_id: str
    source_title: str
    location: str = ""
    excerpt: str = ""
    project_id: str | None = None
    project_name: str | None = None
```

Update existing `KnowledgeSourceDocumentInput(...)` construction in `service.py` to pass the current `project_id` and `project["name"]`.

- [ ] **Step 5: Add all-project collection helper**

In `apps/backend/app/services/knowledge/service.py`, extract current collection into a helper that accepts a project row:

```python
def _collect_project_sources(
    db,
    project,
    request: KnowledgeQueryRequest,
) -> tuple[list[KnowledgeSourceDocumentInput], list[KnowledgeExplorationInput], list[str], list[str], list[str]]:
    project_id = project["id"]
    source_documents: list[KnowledgeSourceDocumentInput] = []
    source_version_ids: list[str] = []
    blockers: list[str] = []
    if request.include_requirements:
        for doc in document_repo.list_by_project(db, project_id):
            if not doc["current_version_id"]:
                continue
            version = document_repo.find_version(db, doc["current_version_id"])
            if not version:
                continue
            markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
            if not markdown_path.exists():
                blockers.append(f"项目「{project['name']}」需求文档「{doc['name']}」当前版本文件不存在。")
                continue
            source_version_ids.append(version["id"])
            source_documents.append(
                KnowledgeSourceDocumentInput(
                    project_id=project_id,
                    project_name=project["name"],
                    document_id=doc["id"],
                    document_name=doc["name"],
                    version_id=version["id"],
                    version_no=version["version_no"],
                    markdown_content=markdown_path.read_text(encoding="utf-8"),
                )
            )

    explorations: list[KnowledgeExplorationInput] = []
    exploration_run_ids: list[str] = []
    if request.include_explorations:
        for run in exploration_repo.list_by_project(db, project_id):
            if run["status"] not in READY_EXPLORATION_STATUSES:
                continue
            exploration_run_ids.append(run["id"])
            artifact_pages, artifact_elements, artifact_blockers = exploration_service._load_run_artifacts(run)
            modules = []
            for module in exploration_repo.list_module_coverages(db, run["id"]):
                module_dict = dict(module)
                module_dict["project_id"] = project_id
                module_dict["project_name"] = project["name"]
                module_dict["pages"] = [page for page in artifact_pages if page["module_key"] == module["module_key"]]
                module_dict["elements"] = [
                    element for element in artifact_elements if element["module_key"] == module["module_key"]
                ]
                module_dict["blockers"] = [
                    blocker for blocker in artifact_blockers if blocker["module_key"] == module["module_key"]
                ]
                modules.append(module_dict)
            explorations.append(
                KnowledgeExplorationInput(
                    exploration_run_id=run["id"],
                    title=f"{project['name']} / {run['title']}",
                    status=run["status"],
                    result_summary=run["result_summary"],
                    modules=modules,
                )
            )
    return source_documents, explorations, source_version_ids, exploration_run_ids, blockers
```

Refactor `_collect_query_input` to call `_collect_project_sources` for the single project.

- [ ] **Step 6: Add all-project stream service**

In `apps/backend/app/services/knowledge/service.py`, add:

```python
async def stream_all_project_knowledge_query(
    actor,
    request: KnowledgeQueryRequest,
) -> AsyncIterator[dict[str, Any]]:
    question = request.question.strip()
    if not question:
        raise api_error(400, "KNOWLEDGE_QUERY_REQUIRED", "请输入要查询的问题。")

    history: list[KnowledgeConversationHistoryMessage] = []
    chat_input = KnowledgeQueryInput(
        project_id="all",
        project_name="全部项目",
        question=question,
        conversation_history=history,
    )

    source_version_ids: list[str] = []
    exploration_run_ids: list[str] = []
    final_output: KnowledgeQueryOutput | None = None

    async def search_project_knowledge(search_question: str) -> KnowledgeQueryOutput:
        nonlocal source_version_ids, exploration_run_ids
        with connect() as db:
            projects = project_repo.list_visible(db, actor)
            source_documents: list[KnowledgeSourceDocumentInput] = []
            explorations: list[KnowledgeExplorationInput] = []
            blockers: list[str] = []
            source_version_ids = []
            exploration_run_ids = []
            for project in projects:
                docs, runs, version_ids, run_ids, project_blockers = _collect_project_sources(db, project, request)
                source_documents.extend(docs)
                explorations.extend(runs)
                source_version_ids.extend(version_ids)
                exploration_run_ids.extend(run_ids)
                blockers.extend(project_blockers)

        input_data = KnowledgeQueryInput(
            project_id="all",
            project_name="全部项目",
            question=search_question.strip(),
            conversation_history=[],
            source_documents=source_documents,
            explorations=explorations,
        )
        if not source_documents and not explorations:
            return KnowledgeQueryOutput(answer="全部项目中没有可用于查询的最终需求文档版本或探索结果。", knowledge_queried=True)
        if blockers and not source_documents and not explorations:
            return KnowledgeQueryOutput(
                answer="无法查询项目知识库：\n\n" + "\n".join(f"- {item}" for item in blockers),
                knowledge_queried=True,
            )
        try:
            output = await knowledge_query_service.run_knowledge_query(input_data)
        except Exception:
            output = _fallback_query_output(input_data)
        output.knowledge_queried = True
        return output

    async for event in knowledge_chat_service.stream_knowledge_chat(chat_input, search_project_knowledge):
        event_type = event.get("type")
        if event_type == "message_delta":
            yield event
        elif event_type == "metadata":
            final_output = event["output"]

    if final_output is None:
        raise ValueError("项目知识库聊天智能体未返回结构化结果。")

    yield {
        "type": "metadata",
        "result": {
            "conversation": None,
            "messages": [],
            "answer": final_output.answer,
            "source_refs": [ref.model_dump() for ref in final_output.source_refs],
            "used_requirement_versions": final_output.used_requirement_versions or source_version_ids,
            "used_exploration_runs": final_output.used_exploration_runs or exploration_run_ids,
            "knowledge_queried": final_output.knowledge_queried,
        },
    }
    yield {"type": "done"}
```

- [ ] **Step 7: Add all-project API route**

In `apps/backend/app/api/v1/knowledge.py`, add a second router before or after the project router:

```python
global_router = APIRouter(prefix="/knowledge", tags=["knowledge"])
```

Add:

```python
@global_router.post("/query/stream")
def stream_all_project_knowledge_query(
    payload: KnowledgeQueryRequest,
    actor=Depends(current_user),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in knowledge_service.stream_all_project_knowledge_query(actor, payload):
                event_type = str(event.get("type") or "message")
                data = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=_json_default)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as exc:
            data = json.dumps(
                {"type": "error", "message": str(exc) or "项目知识库流式查询失败。"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Ensure the app includes both `router` and `global_router`. If API registration imports only `router`, update that registration to include `global_router`.

- [ ] **Step 8: Run backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge_conversations.py -q
```

Expected: PASS.

### Task 2: Wire Frontend Project Scope State

**Files:**
- Modify: `apps/frontend/src/app/(main)/knowledge/page.tsx`
- Modify: `apps/frontend/src/lib/api-client.ts`
- Test: `apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs`

- [ ] **Step 1: Write failing frontend contract tests**

Extend `apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs`:

```javascript
test("knowledge chat input has project scope switcher and no fake thinking toggle", () => {
  assert.match(inputSource, /projectScopeOptions/);
  assert.match(inputSource, /selectedProjectScope/);
  assert.match(inputSource, /onProjectScopeChange/);
  assert.doesNotMatch(inputSource, /thinkingEnabled/);
  assert.doesNotMatch(inputSource, /Clock/);
  assert.doesNotMatch(inputSource, /aria-label="深度思考"/);
});

test("project knowledge page derives input scope from global project context", () => {
  assert.match(pageSource, /scope: globalProjectScope/);
  assert.match(pageSource, /knowledgeScope/);
  assert.match(pageSource, /effectiveKnowledgeScope/);
  assert.match(pageSource, /\/knowledge\/query\/stream/);
  assert.match(pageSource, /\/projects\/\$\{effectiveProjectId\}\/knowledge\/query\/stream/);
  assert.doesNotMatch(pageSource, /currentProjectId \?\? activeProjects\[0\]\?\.id/);
});
```

Expected initially: FAIL until frontend changes are implemented.

- [ ] **Step 2: Run failing frontend test**

Run:

```powershell
node --test apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs
```

Expected: FAIL.

- [ ] **Step 3: Update API types**

In `apps/frontend/src/lib/api-client.ts`, extend `ApiKnowledgeSourceRef`:

```typescript
export type ApiKnowledgeSourceRef = {
  source_type: "requirement" | "exploration" | "manual";
  source_id: string;
  source_title: string;
  location: string;
  excerpt: string;
  project_id: string | null;
  project_name: string | null;
};
```

Allow all-project stream metadata by changing:

```typescript
conversation: ApiKnowledgeConversation;
messages: ApiKnowledgeConversationMessage[];
```

to:

```typescript
conversation: ApiKnowledgeConversation | null;
messages: ApiKnowledgeConversationMessage[];
```

- [ ] **Step 4: Add knowledge scope state**

In `apps/frontend/src/app/(main)/knowledge/page.tsx`, import `scope` from `useProjectContextStore`:

```typescript
const { currentProjectId, hydrate, scope: globalProjectScope } = useProjectContextStore();
```

Add state:

```typescript
const [knowledgeScope, setKnowledgeScope] = useState<"all" | "project">("all");
const [knowledgeProjectId, setKnowledgeProjectId] = useState<string | null>(null);
```

Replace the current fallback:

```typescript
const projectId = currentProjectId ?? activeProjects[0]?.id ?? null;
```

with:

```typescript
const activeCurrentProject = activeProjects.find((project) => project.id === currentProjectId) ?? null;
const effectiveKnowledgeScope =
  globalProjectScope === "project" && activeCurrentProject ? "project" : knowledgeScope;
const effectiveProjectId =
  globalProjectScope === "project"
    ? activeCurrentProject?.id ?? null
    : effectiveKnowledgeScope === "project"
      ? knowledgeProjectId
      : null;
const projectId = effectiveProjectId;
```

Add an effect:

```typescript
useEffect(() => {
  if (globalProjectScope === "project") {
    setKnowledgeScope("project");
    setKnowledgeProjectId(activeCurrentProject?.id ?? currentProjectId ?? null);
    return;
  }
  setKnowledgeScope("all");
  setKnowledgeProjectId(null);
}, [activeCurrentProject?.id, currentProjectId, globalProjectScope]);
```

- [ ] **Step 5: Update query endpoint selection**

In `queryProjectKnowledge`, replace the early project guard:

```typescript
if (!projectId) {
  setError("请先在顶部选择具体项目。");
  return;
}
```

with:

```typescript
if (effectiveKnowledgeScope === "project" && !effectiveProjectId) {
  setError("请先选择可用项目。");
  return;
}
```

Build endpoint:

```typescript
const streamPath =
  effectiveKnowledgeScope === "all"
    ? "/knowledge/query/stream"
    : `/projects/${effectiveProjectId}/knowledge/query/stream`;
```

Use:

```typescript
const response = await fetch(`${API_BASE_URL}${streamPath}`, {
```

When metadata arrives, only set conversation state if `event.result.conversation` is not null:

```typescript
if (event.result.conversation) {
  setActiveProjectConversationId(event.result.conversation.id);
  setProjectConversations((items) => upsertConversation(items, event.result.conversation));
}
```

- [ ] **Step 6: Reset and load conversations by effective project**

Keep conversation loading only for specific project:

```typescript
useEffect(() => {
  if (isCompanyKnowledge || effectiveKnowledgeScope !== "project" || !effectiveProjectId) {
    setProjectConversations([]);
    return;
  }
  void loadProjectConversations(effectiveProjectId);
}, [effectiveKnowledgeScope, effectiveProjectId, isCompanyKnowledge, loadProjectConversations]);
```

Update delete/open handlers to use `effectiveProjectId` and disable them for all-project scope.

### Task 3: Replace Input Controls

**Files:**
- Modify: `apps/frontend/src/components/ui/knowledge-chat-input.tsx`
- Modify: `apps/frontend/src/app/(main)/knowledge/page.tsx`
- Test: `apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs`

- [ ] **Step 1: Add input prop types**

In `knowledge-chat-input.tsx`, add:

```typescript
type KnowledgeProjectScopeOption = {
  value: string;
  label: string;
  locked?: boolean;
};
```

Extend props:

```typescript
projectScopeOptions: KnowledgeProjectScopeOption[];
projectScopeDisabled?: boolean;
selectedProjectScope: string;
onProjectScopeChange: (value: string) => void;
```

- [ ] **Step 2: Remove fake thinking control**

Remove:

```typescript
Clock
```

from imports, remove:

```typescript
const [thinkingEnabled, setThinkingEnabled] = React.useState(false);
```

and delete the entire `aria-label="深度思考"` button.

- [ ] **Step 3: Add project selector in the old plus area**

Replace the old `+` button with:

```tsx
<div className="relative shrink-0">
  <select
    aria-label="选择知识检索项目"
    className={cn(
      "h-7 max-w-40 rounded-md border bg-background px-2 text-xs text-foreground shadow-sm outline-none transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60",
      !compact && "h-8 max-w-48 text-sm",
    )}
    disabled={disabled || loading || projectScopeDisabled || projectScopeOptions.length <= 1}
    onChange={(event) => onProjectScopeChange(event.target.value)}
    title={projectScopeDisabled ? "跟随右上角项目上下文" : "选择知识检索项目"}
    value={selectedProjectScope}
  >
    {projectScopeOptions.map((option) => (
      <option key={option.value} value={option.value}>
        {option.label}
      </option>
    ))}
  </select>
</div>
```

If the app already has a local select pattern preferred for compact inline controls, use that existing component instead of native `select`, but keep the same props and disabled behavior.

- [ ] **Step 4: Shrink model label**

Replace:

```typescript
const modelLabel = selectedModelProvider
  ? `${selectedModelProvider.provider} / ${selectedModelProvider.model}`
```

with:

```typescript
const modelLabel = selectedModelProvider
  ? selectedModelProvider.model
```

Use shorter classes:

```tsx
"inline-flex max-w-40 min-w-0 items-center justify-center gap-1 rounded-md font-medium text-muted-foreground transition-colors duration-200 hover:bg-muted hover:text-foreground"
```

- [ ] **Step 5: Pass project selector props from page**

In `ProjectKnowledgeWorkspace`, add props:

```typescript
projectScopeDisabled: boolean;
projectScopeOptions: Array<{ value: string; label: string }>;
selectedProjectScope: string;
onProjectScopeChange: (value: string) => void;
```

Pass them to both `KnowledgeChatInput` instances.

Build options in page:

```typescript
const knowledgeProjectScopeOptions =
  globalProjectScope === "project" && activeCurrentProject
    ? [{ value: activeCurrentProject.id, label: activeCurrentProject.name }]
    : [
        { value: "all", label: "全部项目" },
        ...activeProjects.map((project) => ({ value: project.id, label: project.name })),
      ];
const selectedProjectScope =
  globalProjectScope === "project"
    ? activeCurrentProject?.id ?? currentProjectId ?? "all"
    : effectiveKnowledgeScope === "all"
      ? "all"
      : knowledgeProjectId ?? "all";
```

Add handler:

```typescript
function changeKnowledgeProjectScope(value: string) {
  if (value === "all") {
    setKnowledgeScope("all");
    setKnowledgeProjectId(null);
    return;
  }
  setKnowledgeScope("project");
  setKnowledgeProjectId(value);
}
```

### Task 4: Source Display, Tests, and Verification

**Files:**
- Modify: `apps/frontend/src/app/(main)/knowledge/page.tsx`
- Test: `apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs`
- Test: `apps/backend/tests/test_knowledge_conversations.py`

- [ ] **Step 1: Show project name in all-project refs**

In the source refs render block, add project badge when present:

```tsx
{ref.project_name ? <Badge variant="secondary">{ref.project_name}</Badge> : null}
```

Place it before the source title so cross-project answers are scannable.

- [ ] **Step 2: Run frontend contract test**

Run:

```powershell
node --test apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Run backend test**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge_conversations.py -q
```

Expected: PASS.

- [ ] **Step 4: Run targeted lint/type check if available**

Inspect package scripts:

```powershell
Get-Content -LiteralPath apps/frontend/package.json
```

If a focused frontend check exists, run it. For example:

```powershell
cd apps/frontend
npm run lint
```

Expected: PASS, or document the exact existing failure if unrelated.

- [ ] **Step 5: Manual UI verification**

Start the frontend/backend using the repo's normal commands.

Verify:

- Top-right `全部项目`, input selector defaults to `全部项目`
- Top-right `全部项目`, input selector can choose a specific project
- Top-right specific project, input selector is locked to that project
- Clock button is gone
- Collapsed model selector shows only the model name
- Specific project chat still loads and deletes history
- All-project query does not show history controls as if it belonged to a specific project

- [ ] **Step 6: Final diff review**

Run:

```powershell
git diff -- apps/backend/app/agents/knowledge_chat/schemas.py apps/backend/app/schemas/knowledge.py apps/backend/app/services/knowledge/service.py apps/backend/app/api/v1/knowledge.py apps/frontend/src/lib/api-client.ts apps/frontend/src/components/ui/knowledge-chat-input.tsx apps/frontend/src/app/(main)/knowledge/page.tsx apps/backend/tests/test_knowledge_conversations.py apps/frontend/tests/knowledge-chat-model-switch-contract.test.mjs
```

Expected: changes match this plan and do not revert unrelated local work.
