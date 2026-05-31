# OpenAI Agents SDK Per-Agent Directory Refactor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current custom agent framework direction with an OpenAI Agents SDK-native layout where each business agent owns one directory containing SDK `Agent` definitions, workflow/manager execution, tools, and guardrails.

**Spec:** `docs/superpowers/specs/2026-06-01-openai-agents-sdk-per-agent-directory-spec.md`

**Architecture:** Use `apps/backend/app/ai_agents/{agent_name}/agent.py|agents.py + workflow.py + tools.py + guardrails.py`. Do not introduce `prompts.py`, thin `runner.py`, `*_agent.py`, or service-level prompt parsing.

**Tech Stack:** FastAPI backend, Python, Pydantic, OpenAI Agents SDK, pytest.

---

### Task 0: Freeze The Wrong Direction

**Files:**
- Inspect: `apps/backend/app/agents/`
- Inspect: `apps/backend/app/services/`
- Inspect: `apps/backend/app/api/`

- [ ] **Step 1: Stop adding old pattern files**

Do not add or extend:

```text
apps/backend/app/agents/*/prompts.py
apps/backend/app/agents/*/runner.py
apps/backend/app/agents/*/*_agent.py
apps/backend/app/services/*_agent_service.py
```

- [ ] **Step 2: Treat existing old-pattern files as migration sources only**

Existing `agent.py`, `prompts.py`, `runner.py`, `AgentDefinition`, and `runtime.py` files may be read to migrate behavior, but should not be expanded as the final design.

- [ ] **Step 3: Do not implement more compatibility wrappers**

Avoid adding thin wrappers whose only job is:

```python
return await run_agent(agent_id, input)
```

### Task 1: Add SDK-Native Root Directory

**Files:**
- Create: `apps/backend/app/ai_agents/__init__.py`
- Create: `apps/backend/app/ai_agents/run_config.py`
- Create: `apps/backend/app/ai_agents/model_provider.py`
- Create: `apps/backend/app/ai_agents/tracing.py`

- [ ] **Step 1: Create root package**

Create:

```text
apps/backend/app/ai_agents/
```

This is the new SDK-native agent root.

- [ ] **Step 2: Add shared run config module**

`shared/run_config.py` should expose:

```python
def build_run_config(agent_name: str, *, actor_id: str | None = None) -> RunConfig:
    ...
```

Initial version may return a minimal `RunConfig` using existing model provider behavior or a documented placeholder if model provider refactor is deferred.

- [ ] **Step 3: Do not move model assignment UI yet**

Existing model assignment service can remain temporarily until all agents migrate. This task only creates the new root.

### Task 2: Add Architecture Tests For New Layout

**Files:**
- Create or modify: `apps/backend/tests/test_ai_agents_architecture.py`

- [ ] **Step 1: Add forbidden file tests**

Assert these do not exist under `app/ai_agents`:

```text
**/prompts.py
**/runner.py
**/*_agent.py
```

- [ ] **Step 2: Add required entrypoint tests**

For every business agent directory under `app/ai_agents`, require:

```text
agent.py or agents.py
workflow.py
```

Ignore `shared`.

- [ ] **Step 3: Add API/service boundary tests**

Assert:

- `app/services/**/*.py` does not directly call `Runner.run`.
- `app/api/**/*.py` does not directly build long agent instructions.
- `app/api/**/*.py` does not import SDK `Agent`.

- [ ] **Step 4: Run expected RED or GREEN**

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_ai_agents_architecture.py -q
```

Expected during early migration: tests for `ai_agents` root should pass once created; service boundary tests may need an allowlist until migration completes.

### Task 3: Migrate `document_editor` First

**Files:**
- Create: `apps/backend/app/ai_agents/document_editor/__init__.py`
- Create: `apps/backend/app/ai_agents/document_editor/agent.py`
- Create: `apps/backend/app/ai_agents/document_editor/workflow.py`
- Create: `apps/backend/app/ai_agents/document_editor/guardrails.py`
- Modify: `apps/backend/app/api/v1/agents.py`
- Eventually delete: old `apps/backend/app/agents/document_editor/*`

- [ ] **Step 1: Create SDK Agent**

In `document_editor/agent.py`, define:

```python
DOCUMENT_EDITOR_INSTRUCTIONS = """
...
"""

document_editor_agent = Agent(
    name="文档修改智能体",
    instructions=DOCUMENT_EDITOR_INSTRUCTIONS,
    output_type=DocumentEditOutput,
)
```

Move durable behavior rules into `DOCUMENT_EDITOR_INSTRUCTIONS`.

- [ ] **Step 2: Create workflow**

In `workflow.py`, define:

```python
async def edit_document(input_data: DocumentEditInput, *, actor_id: str | None = None) -> DocumentEditOutput:
    result = await Runner.run(
        document_editor_agent,
        build_document_editor_input(input_data),
        run_config=build_run_config("document_editor", actor_id=actor_id),
    )
    return DocumentEditOutput.model_validate(result.final_output)
```

The input builder may be a private function inside `workflow.py`, not a separate `prompts.py`.

- [ ] **Step 3: Add basic guardrails**

In `guardrails.py`, add checks for:

- empty document content
- empty instruction
- empty edited output

Wire guardrails into the Agent only if current SDK/provider support is confirmed locally.

- [ ] **Step 4: Update API**

`POST /agents/document-editor/run` should call:

```python
app.ai_agents.document_editor.workflow.edit_document
```

- [ ] **Step 5: Add tests**

Add tests that:

- `document_editor_agent` is an SDK `Agent`
- `output_type` is `DocumentEditOutput`
- no `prompts.py` or `runner.py` exists
- workflow calls `Runner.run`

- [ ] **Step 6: Run focused checks**

Run:

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_ai_agents_architecture.py -q
./.venv/bin/python -m compileall app -q
```

### Task 4: Migrate `requirement_analysis`

**Files:**
- Create: `apps/backend/app/ai_agents/requirement_analysis/__init__.py`
- Create: `apps/backend/app/ai_agents/requirement_analysis/agent.py`
- Create: `apps/backend/app/ai_agents/requirement_analysis/workflow.py`
- Create: `apps/backend/app/ai_agents/requirement_analysis/guardrails.py`
- Modify: current requirement analysis service/API call path

- [ ] **Step 1: Create SDK Agent**

Define `requirement_analysis_agent = Agent(...)` with:

```python
output_type=RequirementAnalysisOutput
```

- [ ] **Step 2: Move durable rules into Agent instructions**

Rules:

- input must be merged requirement working draft
- do not merge sources
- do not generate test cases
- do not generate knowledge base
- identify gaps, assumptions, clarification questions, quality gate

- [ ] **Step 3: Create workflow**

Workflow accepts `RequirementAnalysisInput` and returns `RequirementAnalysisOutput`.

- [ ] **Step 4: Update service**

Service should:

- read requirement version
- call `requirement_analysis.workflow.analyze_requirement`
- save result/logs

Service must not parse agent JSON.

- [ ] **Step 5: Run focused checks**

Run architecture tests and compile.

### Task 5: Migrate `knowledge_builder`

**Files:**
- Create: `apps/backend/app/ai_agents/knowledge_builder/__init__.py`
- Create: `apps/backend/app/ai_agents/knowledge_builder/agent.py`
- Create: `apps/backend/app/ai_agents/knowledge_builder/workflow.py`
- Create: `apps/backend/app/ai_agents/knowledge_builder/tools.py`
- Create: `apps/backend/app/ai_agents/knowledge_builder/guardrails.py`
- Modify: current knowledge builder service call path

- [ ] **Step 1: Create SDK Agent**

Define `knowledge_builder_agent = Agent(...)` with:

```python
output_type=KnowledgeBuildOutput
```

- [ ] **Step 2: Add tools only if model must call them**

If source loading is deterministic and already done by service, do not expose it as a tool yet.

- [ ] **Step 3: Add guardrails**

Guard against:

- unconfirmed questions being written as knowledge
- missing source refs
- empty wiki pages

- [ ] **Step 4: Create workflow**

Workflow accepts `KnowledgeBuildInput` and returns `KnowledgeBuildOutput`.

- [ ] **Step 5: Update service**

Service calls workflow and handles artifact persistence.

### Task 6: Migrate `raw_requirement_converter`

**Files:**
- Create: `apps/backend/app/ai_agents/raw_requirement_converter/__init__.py`
- Create: `apps/backend/app/ai_agents/raw_requirement_converter/agent.py`
- Create: `apps/backend/app/ai_agents/raw_requirement_converter/workflow.py`
- Create: `apps/backend/app/ai_agents/raw_requirement_converter/tools.py`
- Create: `apps/backend/app/ai_agents/raw_requirement_converter/guardrails.py`
- Modify: current upload/conversion call path

- [ ] **Step 1: Separate deterministic conversion from LLM review**

Keep PDF/DOCX/TXT parsing and deterministic Markdown normalization outside the LLM agent unless model tool-calling is explicitly required.

- [ ] **Step 2: Create SDK Agent**

The agent reviews and standardizes candidate Markdown:

```python
raw_requirement_converter_agent = Agent(
    name="格式转换智能体",
    instructions=...,
    output_type=RequirementConversionOutput,
)
```

- [ ] **Step 3: Create workflow**

Workflow receives `RequirementConversionInput`, applies deterministic normalization if needed, then runs the agent.

- [ ] **Step 4: Update service**

Upload/file service calls workflow, then persists converted Markdown.

### Task 7: Redesign `requirement_merge` As Multi-Agent Workflow

**Files:**
- Create: `apps/backend/app/ai_agents/requirement_merge/__init__.py`
- Create: `apps/backend/app/ai_agents/requirement_merge/agents.py`
- Create: `apps/backend/app/ai_agents/requirement_merge/workflow.py`
- Create: `apps/backend/app/ai_agents/requirement_merge/tools.py`
- Create: `apps/backend/app/ai_agents/requirement_merge/guardrails.py`
- Create: `apps/backend/app/ai_agents/requirement_merge/handoffs.py` only if needed
- Modify: current requirement merge services

- [ ] **Step 1: Define sub-agents**

In `agents.py`, define:

```python
outline_agent
assignment_agent
section_merge_agent
conflict_review_agent
coverage_verifier_agent
```

- [ ] **Step 2: Prefer deterministic workflow first**

In `workflow.py`, orchestrate:

```text
source block extraction input
Runner.run(outline_agent, ...)
Runner.run(assignment_agent, ...)
Runner.run(section_merge_agent, ...)
Runner.run(conflict_review_agent, ...)
Runner.run(coverage_verifier_agent, ...)
```

Do not use handoffs until there is a clear need for agent-controlled transfer.

- [ ] **Step 3: Use agents-as-tools only where useful**

If a coordinator agent needs to call a specialist while staying in control, expose the specialist via `agent.as_tool(...)`.

- [ ] **Step 4: Keep deterministic rendering outside Agent**

These remain service/deterministic modules:

- source block extraction
- Markdown artifact rendering
- quality report file write
- version write
- operation log

- [ ] **Step 5: Add guardrails**

Guardrails:

- every source block must be handled
- no `docmap-*` in merged public Markdown
- conflict status cannot produce final merged version
- output section ids must exist in target outline

- [ ] **Step 6: Update merge services**

Services should call `requirement_merge.workflow.merge_requirements(...)`, then handle persistence.

### Task 8: Replace Old Agent Management

**Files:**
- Modify: `apps/backend/app/services/agent_service.py`
- Modify: `apps/backend/app/api/v1/agents.py`
- Possibly create: `apps/backend/app/ai_agents/manifest.py`

- [ ] **Step 1: Create explicit manifest**

Create a manifest listing product agents:

```python
AI_AGENT_MANIFEST = [
    AgentManifestItem(id="document_editor", name="文档修改智能体", ...),
    ...
]
```

- [ ] **Step 2: Model assignment compatibility**

Keep existing model assignment DB schema if needed, keyed by manifest id.

- [ ] **Step 3: Debug endpoint**

If a generic debug endpoint is still needed, route by manifest to SDK Agent objects, not old `AgentDefinition`.

- [ ] **Step 4: Remove dependence on old `app.agents.registry`**

Agent listing should not depend on old custom discovery.

### Task 9: Remove Old Framework

**Files:**
- Delete after migration:
  - `apps/backend/app/agents/definitions.py`
  - `apps/backend/app/agents/registry.py`
  - `apps/backend/app/agents/runtime.py`
  - old `apps/backend/app/agents/{agent}/prompts.py`
  - old `apps/backend/app/agents/{agent}/runner.py`
  - old `apps/backend/app/agents/{agent}/agent.py` if superseded by `ai_agents`

- [ ] **Step 1: Verify no imports remain**

Run:

```bash
rg -n "app\\.agents" apps/backend/app
```

Only allowed references should be temporary migration comments or deleted before completion.

- [ ] **Step 2: Delete old framework files**

Delete only after all product paths use `app.ai_agents`.

- [ ] **Step 3: Run compile**

```bash
cd apps/backend
./.venv/bin/python -m compileall app -q
```

### Task 10: Update Documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-05-31-openai-agents-sdk-architecture-refactor-spec.md`
- Modify: `docs/superpowers/plans/2026-05-31-openai-agents-sdk-architecture-refactor.md`

- [ ] **Step 1: Add superseded notice**

Add a note that the May 31 spec/plan is superseded by:

```text
docs/superpowers/specs/2026-06-01-openai-agents-sdk-per-agent-directory-spec.md
docs/superpowers/plans/2026-06-01-openai-agents-sdk-per-agent-directory.md
```

- [ ] **Step 2: Do not delete historical docs**

Keep history, but clearly mark the current authority.

### Task 11: Verification

**Files:** no planned changes.

- [ ] **Step 1: Run architecture tests**

```bash
cd apps/backend
./.venv/bin/python -m pytest tests/test_ai_agents_architecture.py -q
```

- [ ] **Step 2: Run backend tests**

```bash
cd apps/backend
./.venv/bin/python -m pytest -q
```

- [ ] **Step 3: Run import/compile checks**

```bash
./.venv/bin/python -m compileall app -q
```

- [ ] **Step 4: Manual smoke test**

Verify:

- document editor AI edit
- raw requirement conversion
- requirement analysis
- requirement merge
- knowledge builder
- model assignment list

### Completion Checklist

- [ ] `app/ai_agents` exists and is the primary agent root.
- [ ] Each business agent owns exactly one directory.
- [ ] Simple agents use `agent.py + workflow.py`.
- [ ] Complex agents use `agents.py + workflow.py`.
- [ ] No `prompts.py` under `app/ai_agents`.
- [ ] No thin `runner.py` under `app/ai_agents`.
- [ ] No `*_agent.py` under `app/ai_agents`.
- [ ] Product paths call workflows, not old `run_agent(agent_id, input)`.
- [ ] Old `app/agents` custom framework is removed or explicitly deprecated.
- [ ] Service layer does not write agent instructions.
- [ ] Service layer does not parse agent JSON.
- [ ] Structured outputs use SDK `output_type`.
- [ ] Guardrails are used where they provide real value.
