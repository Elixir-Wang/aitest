---
name: mintlify-api-reference-to-openapi
description: Use when a user needs to convert a Mintlify API reference site, API docs page, /api-reference URL, openApiReferenceData pages, or cybotstar-style documentation into an OpenAPI or Swagger JSON file.
---

# Mintlify API Reference to OpenAPI

## Overview

Use this skill to convert a Mintlify-generated API reference site into an OpenAPI 3.0.3 document. Mintlify pages often embed structured `openApiReferenceData` in Next.js flight data; that structured source is more reliable than scraping visible text.

This skill is for the pre-import step. After generating OpenAPI JSON, hand it to the project OpenAPI parser/import flow instead of replacing that flow.

For Cybotstar-style interface asset import, use the `cybotstar-assets` profile. It keeps the conversion deterministic while adding the post-processing the interface asset UI expects, especially auth headers as visible parameters.

## When to Use

Use this when the source is a documentation site rather than an existing OpenAPI file, especially when the URL looks like:

- `/api-reference/introduction`
- `/api-reference/<group>/<operation>`
- A Mintlify page with `generator="Mintlify"`
- A page containing `openApiReferenceData`
- A page whose metadata has `openapi: "GET /some/path"`

Do not use this skill when the input is already an OpenAPI/Swagger JSON or YAML document. In that case, use the repository's existing OpenAPI import/parser.

## Workflow

1. Confirm the source page is reachable.
2. Fetch the introduction or root API reference page.
3. Discover API pages from `/api-reference/*` links.
4. For each page, prefer embedded `openApiReferenceData`.
5. Convert operations and dependencies into OpenAPI `paths`.
6. When `openApiReferenceData` is missing, fall back only to `pageMetadata.openapi` and mark the operation with `x-source-warning`.
7. Deduplicate by `method + path`; record skipped duplicates in `x-duplicate-operations`.
8. Preserve traceability with `x-source-doc-url` on every generated operation.
9. For `--profile cybotstar-assets`, expand API key security schemes into header parameters with `x-source: security`.
10. Validate that the result has `openapi`, `info`, and non-empty `paths`.
11. If working in `D:\project\test_project`, optionally validate with `apps/backend/app/services/api_automation/openapi_parser.py`.

## Script

Use the bundled script for the deterministic conversion:

```powershell
python .agents\skills\mintlify-api-reference-to-openapi\scripts\mintlify_to_openapi.py `
  --root-url http://192.168.160.65:30000/api-reference/introduction `
  --output docs\generated\cybotstar-openapi.generated.json `
  --title "Cybotstar OpenAPI" `
  --profile cybotstar-assets
```

Useful flags:

- `--max-pages 10` for a quick smoke test.
- `--timeout 20` when the docs site is slow.
- `--no-fallback` to exclude pages without structured `openApiReferenceData`.
- `--profile generic` for plain Mintlify conversion without interface-asset adjustments.
- `--profile cybotstar-assets` when regenerating Cybotstar interface assets or comparing against `cybotstar-openapi.generated.json`.

## Output Expectations

The generated file should include:

- `openapi: "3.0.3"`
- `info.title`, `info.version`, and source description
- `paths` grouped by HTTP path and method
- `components.securitySchemes` when security dependencies can be mapped
- `x-generated-from`
- `x-source-page-count`
- `x-imported-operation-count`
- `x-minimal-operations`
- `x-duplicate-operations`
- `x-adjusted-for-interface-assets` when using `--profile cybotstar-assets`

Each operation should include:

- `operationId` when available
- `summary` and `description` when available
- `tags`
- `parameters`
- `requestBody`
- `responses`
- `security`
- `x-source-doc-url`

## Common Mistakes

- Do not scrape rendered prose first. Check embedded `openApiReferenceData` before using text extraction.
- Do not silently invent request bodies, response schemas, or auth headers. If the source lacks structure, generate a minimal operation and mark it.
- Do not remove traceability fields. They are needed to audit imperfect conversions.
- Do not assume every API page has structured data. Some Mintlify pages only expose `pageMetadata.openapi`.
- Do not treat duplicate operations as harmless. Keep the first operation and report the duplicate source page.
- Do not compare only operation counts. Also compare `method + path`, `requestBody` count, header parameters, security schemes, `x-minimal-operations`, and duplicates.
- Do not use Cybotstar post-processing for unrelated Mintlify sites unless the target system also wants auth headers visible as parameters.

## Project Handoff

For `D:\project\test_project`, the generated JSON can be consumed by the existing OpenAPI parser/import implementation under:

```text
apps/backend/app/services/api_automation/openapi_parser.py
```

That parser expects a valid OpenAPI/Swagger document with a non-empty `paths` object. This skill produces that input; it does not replace the parser.
