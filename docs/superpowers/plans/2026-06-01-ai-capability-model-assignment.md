# AI Capability Model Assignment Refactor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. This migration intentionally does not preserve old model-assignment APIs or the old `agent_model_assignments` runtime contract.

**Goal:** Replace agent-only model assignment with a unified AI Capability model assignment system covering both Agents SDK agents and plain OpenAI SDK LLM tasks.

**Spec:** `docs/superpowers/specs/2026-06-01-ai-capability-model-assignment-spec.md`

**Architecture:** Use `apps/backend/app/ai_runtime/capabilities.py` as the single AI capability registry. Use `model_assignments.capability_id` for model assignment. Keep `ai_agents/` only for real Agents SDK agents and move `document_editor` to `llm_tasks/`.

**Tech Stack:** FastAPI backend, SQLite, Python, Pydantic, OpenAI SDK, OpenAI Agents SDK, Next.js frontend, pytest.

---

## File Map

- Create: `apps/backend/app/ai_runtime/__init__.py`
- Create: `apps/backend/app/ai_runtime/capabilities.py`
- Create: `apps/backend/app/ai_runtime/model_selection.py`
- Create: `apps/backend/app/ai_runtime/openai_client.py`
- Create: `apps/backend/app/ai_runtime/run_config.py`
- Create: `apps/backend/app/llm_tasks/__init__.py`
- Create: `apps/backend/app/llm_tasks/document_editor.py`
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/app/repositories/model_repo.py`
- Modify: `apps/backend/app/services/model_service.py`
- Modify: `apps/backend/app/services/agent_service.py`
- Modify: `apps/backend/app/api/v1/models.py`
- Modify: `apps/backend/app/api/v1/agents.py`
- Modify: `apps/backend/app/main.py` only if new router registration is needed.
- Modify: `apps/backend/app/services/*` callers that currently use `ai_agents.document_editor.workflow`.
- Modify: `apps/frontend/src/app/(main)/settings/models/assignments/page.tsx`
- Modify: frontend API types if model assignment DTOs are centralized.
- Delete: `apps/backend/app/ai_agents/manifest.py`
- Delete: `apps/backend/app/ai_agents/model_provider.py`
- Delete: `apps/backend/app/ai_agents/run_config.py`
- Delete: `apps/backend/app/ai_agents/document_editor/`
- Delete runtime use of `agent_model_assignments`.

---

## Design Decisions

- `AiCapability.kind` has only `agent` and `llm_task`.
- `workflow` is not a capability kind; it is an internal entrypoint for a capability.
- Global capability metadata contains no `skill_ids`.
- Skill/tool configuration remains inside each agent directory.
- `document_editor` is a `llm_task`, not an agent.
- No default model fallback is allowed.
- Frontend business calls never send `model`, `api_key`, or `base_url`.
- Model assignment is by `capability_id`, not `agent_id`.
- Old model assignment APIs are deleted, not wrapped.

---

## Task 1: Add Unified AI Capability Registry

**Files:**
- Create: `apps/backend/app/ai_runtime/__init__.py`
- Create: `apps/backend/app/ai_runtime/capabilities.py`
- Modify or delete: `apps/backend/app/ai_agents/manifest.py`
- Modify: `apps/backend/tests/test_ai_agent_model_assignments.py`
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Create `AiCapability` dataclass**

Define:

```python
@dataclass(frozen=True)
class AiCapability:
    id: str
    name: str
    description: str
    kind: Literal["agent", "llm_task"]
```

- [ ] **Step 2: Create `AI_CAPABILITIES`**

Include:

```text
document_editor                  kind=llm_task
raw_requirement_format_converter kind=agent
requirement_merge                kind=agent
requirement_analysis             kind=agent
site_exploration                 kind=agent
knowledge_builder                kind=agent
```

- [ ] **Step 3: Add registry helpers**

Expose:

```python
list_ai_capabilities()
get_ai_capability(capability_id)
list_agent_capabilities()
list_llm_task_capabilities()
```

- [ ] **Step 4: Replace `ai_agents.manifest` imports**

Update backend imports that read `list_ai_agents()` / `get_ai_agent()` to read from `ai_runtime.capabilities`.

Delete `apps/backend/app/ai_agents/manifest.py` after all imports are replaced.

- [ ] **Step 5: Add tests**

Assert:

- `document_editor` exists and has `kind == "llm_task"`.
- Agent capability list excludes `document_editor`.
- Capability IDs are unique.
- Capability kinds are only `agent` or `llm_task`.

---

## Task 2: Replace Agent-Only Assignment Table

**Files:**
- Modify: `apps/backend/app/seed/init_db.py`
- Modify: `apps/backend/app/repositories/model_repo.py`
- Modify: tests that initialize or inspect model assignment data.

- [ ] **Step 1: Create `model_assignments` table**

Target schema:

```sql
CREATE TABLE IF NOT EXISTS model_assignments (
  capability_id TEXT PRIMARY KEY,
  model_provider_id TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(model_provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
);
```

- [ ] **Step 2: Migrate data**

During startup/database migration:

```sql
INSERT OR REPLACE INTO model_assignments (capability_id, model_provider_id, updated_at)
SELECT agent_id, model_provider_id, updated_at
FROM agent_model_assignments;
```

Only run this if `agent_model_assignments` exists.

- [ ] **Step 3: Drop old table**

After migration:

```sql
DROP TABLE agent_model_assignments;
```

- [ ] **Step 4: Replace repository functions**

Remove old agent-only functions:

```python
list_agent_assignments
find_agent_assignment
upsert_agent_assignment
```

Add:

```python
list_model_assignments
find_model_assignment
upsert_model_assignment
```

- [ ] **Step 5: Add repository tests**

Cover:

- listing assignments joins `model_providers`
- finding one assignment by `capability_id`
- upserting assignment
- disabled provider rejection handled at service layer

---

## Task 3: Add Runtime Model Selection

**Files:**
- Create: `apps/backend/app/ai_runtime/model_selection.py`
- Create: `apps/backend/app/ai_runtime/openai_client.py`
- Create: `apps/backend/app/ai_runtime/run_config.py`
- Delete: `apps/backend/app/ai_agents/model_provider.py`
- Delete: `apps/backend/app/ai_agents/run_config.py`

- [ ] **Step 1: Implement `ModelSelection`**

Define:

```python
@dataclass(frozen=True)
class ModelSelection:
    capability_id: str
    capability_kind: Literal["agent", "llm_task"]
    model_provider_id: str
    provider: str
    model: str
    base_url: str | None
    api_key: str
    model_status: str
```

- [ ] **Step 2: Implement `resolve_model_selection`**

Rules:

- unknown capability -> business error
- missing assignment -> business error
- missing provider -> business error
- disabled provider -> business error
- empty api key -> business error
- no default model fallback

- [ ] **Step 3: Implement OpenAI client builder**

In `openai_client.py`:

```python
def build_openai_client(selection: ModelSelection) -> OpenAI:
    ...
```

- [ ] **Step 4: Implement Agents SDK run config builder**

In `run_config.py`:

```python
def build_agent_run_config(capability_id: str, *, actor_id: str | None = None, trace_metadata: dict[str, Any] | None = None) -> RunConfig:
    ...
```

Reject `capability_kind != "agent"`.

- [ ] **Step 5: Update agent workflows**

Update existing `ai_agents/*/workflow.py` imports from old `app.ai_agents.run_config` to `app.ai_runtime.run_config`.

- [ ] **Step 6: Delete old modules**

Remove old `ai_agents/model_provider.py` and `ai_agents/run_config.py` after all imports are moved.

---

## Task 4: Replace Backend Model Assignment API

**Files:**
- Modify: `apps/backend/app/schemas/model.py`
- Modify: `apps/backend/app/api/v1/models.py`
- Modify: `apps/backend/app/api/v1/agents.py`
- Modify: `apps/backend/app/services/model_service.py`
- Modify: `apps/backend/app/services/agent_service.py`
- Modify: `apps/backend/app/main.py` if a new `ai` router is added.

- [ ] **Step 1: Add capability DTOs**

Add response DTOs for:

```text
AiCapabilityOut
ModelAssignmentOut
ModelAssignmentIn
```

`ModelAssignmentOut` includes capability metadata plus current assignment fields.

- [ ] **Step 2: Add capability endpoint**

Implement:

```text
GET /ai/capabilities
```

or place under existing API organization if this repo already has a preferred `ai` router pattern.

- [ ] **Step 3: Add model assignment endpoints**

Implement:

```text
GET /model-assignments
PUT /model-assignments/{capability_id}
```

- [ ] **Step 4: Delete old endpoints**

Remove:

```text
GET /agents/model-assignments
PUT /agents/{agent_id}/model-assignment
```

- [ ] **Step 5: Adjust `/agents`**

Ensure `/agents` returns only `kind == "agent"` capabilities.

- [ ] **Step 6: Update operation logs**

Model assignment change logs use:

```text
object_type = model_assignment
object_id = capability_id
summary = 配置 AI 能力模型：{capability_name}
```

---

## Task 5: Move `document_editor` To LLM Task

**Files:**
- Create: `apps/backend/app/llm_tasks/__init__.py`
- Create: `apps/backend/app/llm_tasks/document_editor.py`
- Modify: `apps/backend/app/schemas/document_editor.py` only if needed.
- Modify: services/API callers currently importing `app.ai_agents.document_editor.workflow`.
- Delete: `apps/backend/app/ai_agents/document_editor/`

- [ ] **Step 1: Implement `llm_tasks.document_editor.edit_document`**

Use:

```python
selection = resolve_model_selection("document_editor")
client = build_openai_client(selection)
```

Then call the OpenAI SDK with structured output for `DocumentEditOutput`.

- [ ] **Step 2: Move validation into local functions**

Preserve current validation intent:

- input document cannot be empty
- instruction cannot be empty
- output status must be valid
- edited content cannot be unexpectedly empty
- warnings explain unsupported fact additions

- [ ] **Step 3: Update callers**

Replace imports of:

```python
app.ai_agents.document_editor.workflow.edit_document
```

with:

```python
app.llm_tasks.document_editor.edit_document
```

- [ ] **Step 4: Delete agent implementation**

Delete:

```text
apps/backend/app/ai_agents/document_editor/
```

- [ ] **Step 5: Add tests**

Assert:

- `document_editor` does not appear in `/agents`
- `document_editor` appears in `/model-assignments`
- document editor resolves model selection through `document_editor`
- document editor does not call Agents SDK `Runner.run`

---

## Task 6: Update Frontend Model Assignment Page

**Files:**
- Modify: `apps/frontend/src/app/(main)/settings/models/assignments/page.tsx`
- Modify: frontend API client/types if assignment DTOs are shared.

- [ ] **Step 1: Replace API calls**

Remove calls to:

```text
/agents/model-assignments
/agents/{agent_id}/model-assignment
```

Use:

```text
/model-assignments
/model-assignments/{capability_id}
```

- [ ] **Step 2: Rename page copy**

Use:

```text
AI 能力模型分配
```

- [ ] **Step 3: Group by `kind`**

Render:

```text
普通 LLM 能力
智能体
```

- [ ] **Step 4: Preserve existing model provider picker behavior**

Provider list still comes from:

```text
/models/providers
```

Only enabled providers should be assignable.

- [ ] **Step 5: Add/update tests or manual checks**

Verify:

- document editor appears under normal LLM abilities
- agents appear under agents
- assignment save and refresh works
- browser network has no old assignment endpoints

---

## Task 7: Architecture And Cleanup Tests

**Files:**
- Modify: `apps/backend/tests/test_ai_agent_model_assignments.py`
- Modify: `apps/backend/tests/test_ai_agents_architecture.py`
- Add: `apps/backend/tests/test_ai_capabilities.py`
- Add: `apps/backend/tests/test_model_selection.py`
- Add/update frontend tests if this repo has a current pattern.

- [ ] **Step 1: Add capability architecture tests**

Assert:

- `AI_CAPABILITIES` IDs are unique
- all kinds are valid
- `document_editor` is `llm_task`
- `/agents` excludes `llm_task`

- [ ] **Step 2: Add model assignment tests**

Assert:

- `/model-assignments` returns all capabilities
- updating unknown capability fails
- disabled provider fails
- successful update logs correct object type

- [ ] **Step 3: Add model selection tests**

Assert:

- missing assignment fails clearly
- disabled provider fails clearly
- missing api key fails clearly
- successful selection includes model/provider/base_url/api_key

- [ ] **Step 4: Add cleanup tests**

Assert no backend runtime imports remain for:

```text
app.ai_agents.manifest
app.ai_agents.model_provider
app.ai_agents.run_config
app.ai_agents.document_editor
```

Assert no frontend source contains:

```text
/agents/model-assignments
/model-assignment
```

Except deleted files or test fixtures intentionally checking absence.

---

## Task 8: Verification

**Files:**
- No production file ownership; run checks.

- [ ] **Step 1: Backend tests**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest tests/test_ai_capabilities.py tests/test_model_selection.py tests/test_ai_agent_model_assignments.py tests/test_ai_agents_architecture.py -q
```

- [ ] **Step 2: Backend import check**

Run:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m compileall app -q
```

- [ ] **Step 3: Frontend checks**

Run the repo's current frontend validation command from `apps/frontend/package.json`.

At minimum:

```powershell
cd apps/frontend
npm run lint
```

Use the actual available script if `lint` is not present.

- [ ] **Step 4: Browser verification**

Start backend/frontend using the normal repo entrypoints, then verify:

- `/settings/models/assignments` loads
- title is `AI 能力模型分配`
- `文档修改` appears under `普通 LLM 能力`
- agent capabilities appear under `智能体`
- saving a model assignment refreshes correctly
- no old assignment endpoint requests appear in browser network logs

---

## Acceptance Criteria

- [ ] `agent_model_assignments` is migrated to `model_assignments` and no runtime code depends on the old table.
- [ ] Old model assignment endpoints are removed.
- [ ] Frontend no longer calls old model assignment endpoints.
- [ ] `AiCapability` is the single capability registry.
- [ ] `/agents` returns only true agent capabilities.
- [ ] `/model-assignments` returns both agents and LLM tasks.
- [ ] `document_editor` is implemented under `llm_tasks` using OpenAI SDK.
- [ ] `document_editor` no longer uses Agents SDK `Runner.run`.
- [ ] Agents SDK workflows use `ai_runtime.run_config`.
- [ ] Plain LLM tasks use `ai_runtime.model_selection` and `ai_runtime.openai_client`.
- [ ] No default model fallback exists when a capability has no assignment.
- [ ] Backend and frontend verification commands pass.
