# Product architecture

## Backend flow

1. Accept selected endpoint IDs at the product boundary, or selected case IDs only when the service verifies and groups them by endpoint.
2. Authorize project access and reject cross-project endpoint/case IDs.
3. Load the current stored cases for each selected endpoint.
4. Group by endpoint and call a deterministic generator.
5. Update the project's fixed suite directory and return one artifact per endpoint.
6. Persist the current endpoint script artifact used by the runner.
7. Run only persisted artifact IDs and inject the selected environment at execution time.

Do not ask an LLM to write framework boilerplate. Use the generation skill/agent for test-case reasoning, then deterministic templates for executable Python.

## Frontend flow

1. Keep endpoint selection as the primary user model.
2. Disable generation until at least one endpoint with cases is selected.
3. Resolve all current case IDs under the selected endpoints, or send endpoint IDs when the backend supports that contract.
4. Show progress while the request runs and prevent duplicate submissions.
5. On success, switch to the script view and show only the artifacts updated by this action.
6. Preserve endpoint selection so the user can regenerate after editing cases.
7. Surface backend validation errors directly; do not silently broaden selection.

## Idempotency and concurrency

- Serialize writes per project suite or use atomic file replacement.
- Treat endpoint generation as an upsert keyed by project plus endpoint.
- A retry with unchanged cases must produce the same paths and content.
- Concurrent updates to different endpoints may proceed only when shared file writes are protected; otherwise use a project-level lock.
