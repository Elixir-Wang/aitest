---
name: pytest-requests-api-automation
description: Design, implement, or review project-scoped incremental API automation code generation with pytest and Requests. Use when a user asks to generate pytest + requests scripts from selected API cases or OpenAPI endpoints, maintain one automation suite per project, append newly added endpoints, update existing endpoint code, or define the frontend/backend architecture for API script generation.
---

# Pytest + Requests API Automation

Build on verified endpoint definitions, stored API cases, existing routes, schemas, repositories, and UI contracts. Do not guess endpoints or create a parallel automation subsystem when the product already has one.

## Required workflow

1. Inspect the real OpenAPI parser, API-case schema, script persistence, runner, frontend client, and page selection state.
2. Confirm the generation unit: one project owns one suite; one endpoint owns one test module and one data file.
3. Read [best-practices.md](references/best-practices.md) before changing generated code structure.
4. Read [product-architecture.md](references/product-architecture.md) when implementing the click-to-generate workflow or API contracts.
5. Generate only from selected endpoint IDs and the stored cases belonging to those endpoints.
6. Use stable endpoint identity for file ownership. Regenerating an endpoint must update only its files; a new endpoint must append files without deleting other endpoint artifacts.
7. Keep runtime environment values outside generated code. Inject base URL, authentication, secrets, timeout, TLS behavior, and files through environment/configuration.
8. Validate with focused generator tests, pytest collection of a generated suite, service tests, and frontend contract tests.

## Generated suite contract

Use this shape unless the repository already defines a compatible equivalent:

```text
<project>/api_automation/pytest_requests/
├── pyproject.toml
├── pytest.ini
├── conftest.py
├── support/
│   ├── client.py
│   ├── auth.py
│   └── assertions.py
├── data/test_<endpoint-key>.json
└── tests/test_<endpoint-key>.py
```

Keep shared transport, auth, and assertion behavior in `support/`. Keep business cases as data. Parameterize each case so pytest reports failures independently; never loop over every project case inside every endpoint test.

## Update rules

- Derive the endpoint file key from stable endpoint identity plus a readable method/path slug.
- Write files atomically.
- Replace only the selected endpoint's module and data file.
- Preserve files for unselected endpoints.
- Return the exact artifacts updated in the current request.
- Avoid duplicate script records for individual cases when the executable unit is an endpoint module.
- Never embed plaintext credentials, environment URLs, tokens, cookies, or local absolute upload paths.

## Quality gate

Reject the implementation if it creates a fresh suite directory per click, makes one test execute all data files, generates one duplicate script record per case, silently includes unselected endpoints, or cannot collect the generated pytest suite.
