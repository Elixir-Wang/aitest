# Mintlify Labeled HTML Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import explicitly documented Mintlify API pages that lack structured OpenAPI metadata, including the Multi-Agent SSE endpoint.

**Architecture:** Preserve structured metadata as the primary source, then use a strict HTML fallback only when the page explicitly labels one HTTP method and one `/openapi/` request address. Convert labeled header/form tables and SSE examples without inventing undocumented fields, and report pages that still cannot be parsed.

**Tech Stack:** Python standard library, OpenAPI 3.0.3, `unittest`.

---

### Task 1: Add SSE HTML fallback tests

**Files:**
- Create: `.agents/skills/mintlify-api-reference-to-openapi/tests/test_mintlify_to_openapi.py`

- [ ] Add a representative HTML fixture with labeled method, URL, header table, multipart fields, nested JSON fields, JSON response schema, and SSE example.
- [ ] Assert the fallback produces `POST /openapi/v1/gw/multi-agent/sse`, four headers, multipart form data, and `text/event-stream` response metadata.
- [ ] Assert an unlabeled documentation page is not converted.
- [ ] Run `python -m unittest .agents/skills/mintlify-api-reference-to-openapi/tests/test_mintlify_to_openapi.py -v` and confirm RED.

### Task 2: Implement strict labeled HTML parsing

**Files:**
- Modify: `.agents/skills/mintlify-api-reference-to-openapi/scripts/mintlify_to_openapi.py`

- [ ] Add a standard-library HTML collector for headings, labeled values, tables, and code blocks.
- [ ] Require a unique labeled HTTP method and `/openapi/` request address.
- [ ] Convert header and multipart tables, preserving required flags, descriptions, defaults, and nested `data` JSON structure.
- [ ] Represent SSE as `text/event-stream`, keeping the wire body as a string and the event payload schema in `x-event-data-schema`.
- [ ] Add `x-source-extraction`, `x-html-fallback-operations`, and `x-skipped-pages` traceability.
- [ ] Run the focused unit tests and confirm GREEN.

### Task 3: Document and validate the converter

**Files:**
- Modify: `.agents/skills/mintlify-api-reference-to-openapi/SKILL.md`
- Modify: `.agents/skills/mintlify-api-reference-to-openapi/evals/evals.json`

- [ ] Document the strict fallback order and safety rules.
- [ ] Add an evaluation covering a labeled MDX SSE page without `openApiReferenceData`.
- [ ] Regenerate `docs/generated/cybotstar-openapi.generated.json`.
- [ ] Validate the project parser reports two Multi-Agent endpoints.

