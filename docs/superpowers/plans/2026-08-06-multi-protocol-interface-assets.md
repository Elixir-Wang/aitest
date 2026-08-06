# Multi-Protocol Interface Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and import HTTP, SSE, and WebSocket interface assets without dropping WebSocket documentation pages.

**Architecture:** Keep OpenAPI as the canonical document for HTTP and SSE, use AsyncAPI 3.0 for WebSocket, and normalize both formats into the existing API asset domain. Preserve old OpenAPI import behavior while adding protocol-aware metadata, send/receive operations, and a unified document dispatcher.

**Tech Stack:** Python, pytest, OpenAPI 3.0.3 compatibility, AsyncAPI 3.0 JSON, SQLite schema migrations, existing Mintlify HTML/Next flight extraction.

## Global Constraints

- Do not overload HTTP `method` with `WSS`.
- Existing HTTP and SSE imports must remain backward compatible.
- WebSocket assets must preserve source URL, connection URL, send schema, and receive schema.
- Existing user changes in the working tree must not be reverted.
- Add regression tests before implementation and run targeted tests before broad tests.

---

### Task 1: Add generator protocol fixtures and failing tests

**Files:**
- Modify: `D:/project/test_project/.agents/skills/mintlify-api-reference-to-openapi/tests/test_mintlify_to_openapi.py`
- Modify: `D:/project/skills/mintlify-api-reference-to-openapi/evals/evals.json`

**Interfaces:**
- Consumes: existing HTML extraction helpers in `mintlify_to_openapi.py`.
- Produces: failing tests for WebSocket discovery, AsyncAPI operation shape, and preserved SSE behavior.

- [ ] **Step 1: Add a WSS HTML fixture matching the documentation page**
- [ ] **Step 2: Assert WSS pages produce a realtime operation instead of `x-skipped-pages`**
- [ ] **Step 3: Assert generated WebSocket output has server, channel, send message, and receive message schemas**
- [ ] **Step 4: Run the skill tests and verify the new tests fail for the missing WebSocket behavior**

### Task 2: Add protocol-aware Mintlify generation

**Files:**
- Modify: `D:/project/skills/mintlify-api-reference-to-openapi/scripts/mintlify_to_openapi.py`
- Modify: `D:/project/test_project/.agents/skills/mintlify-api-reference-to-openapi/scripts/mintlify_to_openapi.py`
- Modify: both corresponding `SKILL.md` files

**Interfaces:**
- Consumes: discovered Mintlify pages and existing structured/HTML extraction.
- Produces: HTTP/SSE OpenAPI output plus WebSocket AsyncAPI output or a manifest bundle, with `protocol` and source provenance.

- [ ] **Step 1: Detect `WSS`/`WS` page protocol and explicit WebSocket addresses**
- [ ] **Step 2: Extract send and receive code blocks/tables into JSON Schemas without inventing undocumented fields**
- [ ] **Step 3: Emit AsyncAPI 3.0 WebSocket channels and operations while retaining page traceability**
- [ ] **Step 4: Emit a manifest that identifies generated OpenAPI and AsyncAPI documents and protocol counts**
- [ ] **Step 5: Keep HTTP and SSE generation unchanged except for explicit protocol metadata**
- [ ] **Step 6: Run generator tests and verify all protocol fixtures pass**

### Task 3: Add failing backend parser/import tests

**Files:**
- Modify: `D:/project/test_project/apps/backend/tests/test_api_automation_openapi_import.py`
- Create: `D:/project/test_project/apps/backend/tests/test_api_automation_asyncapi_import.py`

**Interfaces:**
- Consumes: generated AsyncAPI 3.0 fixture and existing temporary database helpers.
- Produces: failing tests for AsyncAPI parsing, WebSocket endpoint normalization, document dispatch, and backward-compatible HTTP/SSE behavior.

- [ ] **Step 1: Define an AsyncAPI WebSocket fixture with send and receive messages**
- [ ] **Step 2: Assert parser returns `protocol=websocket` and two directional operations**
- [ ] **Step 3: Assert import persists one document and two endpoint assets without HTTP method coercion**
- [ ] **Step 4: Assert existing OpenAPI HTTP and SSE fixtures still import successfully**
- [ ] **Step 5: Run the focused backend tests and verify the new tests fail**

### Task 4: Implement protocol-neutral backend asset normalization

**Files:**
- Create: `D:/project/test_project/apps/backend/app/services/api_automation/asyncapi_parser.py`
- Modify: `D:/project/test_project/apps/backend/app/services/api_automation/openapi_parser.py`
- Modify: `D:/project/test_project/apps/backend/app/services/api_automation/service.py`
- Modify: `D:/project/test_project/apps/backend/app/repositories/api_automation_repo.py`
- Modify: `D:/project/test_project/apps/backend/app/seed/schema.py`
- Modify: `D:/project/test_project/apps/backend/app/seed/seeds.py` if migration support requires it

**Interfaces:**
- Consumes: OpenAPI documents, AsyncAPI documents, and existing repository persistence functions.
- Produces: `parse_interface_document`, protocol-aware document metadata, endpoint `protocol`, `operation_action`, `address`, and message schema fields.

- [ ] **Step 1: Add additive schema columns with safe defaults for existing rows**
- [ ] **Step 2: Add AsyncAPI parser for servers, channels, messages, and send/receive operations**
- [ ] **Step 3: Add document format detection and unified parsing dispatch**
- [ ] **Step 4: Extend repository create/upsert/serialization functions with protocol-aware fields**
- [ ] **Step 5: Preserve existing HTTP method/path deduplication and add WebSocket directional deduplication**
- [ ] **Step 6: Run focused backend tests and verify the new tests pass**

### Task 5: Expose protocol-aware assets and verify migration

**Files:**
- Modify: `D:/project/test_project/apps/backend/app/schemas/api_automation.py`
- Modify: `D:/project/test_project/apps/backend/app/api/v1/api_automation.py`
- Modify: `D:/project/test_project/apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- Modify: relevant frontend API types/client files only if required by existing patterns

**Interfaces:**
- Consumes: serialized protocol-aware endpoint assets from Task 4.
- Produces: API responses and UI display that distinguish HTTP, SSE, and WebSocket without breaking existing filters.

- [ ] **Step 1: Add protocol fields to response/request schemas with backward-compatible defaults**
- [ ] **Step 2: Add protocol filtering/display and WebSocket send/receive labels in the asset UI**
- [ ] **Step 3: Run backend schema/API tests and existing frontend contract tests**
- [ ] **Step 4: Run full targeted regression suite and inspect generated asset counts**
