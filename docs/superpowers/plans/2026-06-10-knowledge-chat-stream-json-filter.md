# Knowledge Chat Stream JSON Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure project knowledge chat streams user-visible natural language while keeping `KnowledgeQueryOutput` JSON in metadata only.

**Architecture:** Keep LangChain as the streaming tool-calling chat agent and keep Codex CLI agentic search inside the `search_project_knowledge` tool. The backend stream layer will suppress structured JSON chunks, extract the final answer from structured output or final assistant messages, and emit source metadata separately.

**Tech Stack:** FastAPI SSE, LangChain `create_agent`, Pydantic `KnowledgeQueryOutput`, pytest, Biome lint.

---

### Task 1: Backend Stream JSON Suppression

**Files:**
- Modify: `apps/backend/tests/test_knowledge_chat_agent.py`
- Modify: `apps/backend/app/agents/knowledge_chat/service.py`

- [x] **Step 1: Write the failing test**

Add a test where LangChain streams a JSON-looking `KnowledgeQueryOutput` payload and then provides structured metadata. Expected behavior: no JSON `message_delta`; only the `answer` text is emitted.

- [x] **Step 2: Run the focused test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_knowledge_chat_agent.py::test_knowledge_chat_service_does_not_stream_structured_json_chunks -q -p no:cacheprovider`

Expected: FAIL because current stream forwards the raw JSON chunks.

- [x] **Step 3: Implement minimal stream filtering**

Update `stream_knowledge_chat` so it buffers JSON-looking message chunks and, when structured output arrives, emits only `output.answer`. Preserve normal natural-language streaming.

- [x] **Step 4: Run backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_knowledge_chat_agent.py tests\test_knowledge_conversations.py -q --basetemp .pytest-tmp -p no:cacheprovider`

Expected: PASS.

### Task 2: Frontend SSE Guard

**Files:**
- Modify: `apps/frontend/src/app/(main)/knowledge/page.tsx`

- [x] **Step 1: Inspect whether frontend can receive JSON deltas**

Confirm frontend appends `message_delta` directly into the assistant bubble.

- [x] **Step 2: Keep frontend simple**

No frontend JSON parsing should be added unless backend tests show an unavoidable transport issue. Backend owns the contract that `message_delta` is user-visible text only.

- [x] **Step 3: Run frontend lint**

Run: `npm run lint -- "src/app/(main)/knowledge/page.tsx" "src/lib/api-client.ts"`

Expected: PASS.
