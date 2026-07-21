# Test Point Public ID Removal Implementation Plan

> **For agentic workers:** Execute inline with TDD; do not commit without explicit user request.

**Goal:** Remove test-point keys from the public UI/API while preserving internal identity behavior.

**Architecture:** Keep `point_key` in persistence and Markdown flows. Split internal row serialization from public response serialization, and update the dialog header to place the title after badges.

**Tech Stack:** Next.js, React, TypeScript, FastAPI services, pytest, Node test runner.

## Tasks
- [x] Add failing frontend contract tests for header layout and field removal.
- [x] Add failing backend service tests for hidden public keys and stable internal IDs.
- [x] Update dialog header and frontend API type.
- [x] Split backend internal/public serialization.
- [x] Run targeted frontend and backend tests.
