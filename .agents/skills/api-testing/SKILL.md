---
name: api-testing
description: Design risk-focused API test plans, API test cases, smoke/regression scopes, and release-blocking checks for REST, GraphQL, gRPC, SOAP, WebSocket, OpenAPI/Swagger, Postman/curl, or informal interface descriptions. Use when the user asks for API 测试, 接口测试, API 用例, API 测试方案, API 风险分析, API 自动化覆盖建议, or wants to turn interface docs and business context into executable QA coverage.
---

# API Testing

Use this skill to produce API testing outputs that are specific, risk-prioritized, and executable. Prefer verified interface documents, code, OpenAPI/Swagger, Postman collections, curl examples, existing tests, or project routes over naming guesses.

## Workflow

1. Collect real context before designing coverage.
   - Inspect supplied API docs, OpenAPI/Swagger files, route definitions, schemas, existing tests, clients, and service code when available.
   - Separate confirmed facts from inferred assumptions.
   - Ask only for missing information that materially changes the test strategy; otherwise provide a usable first pass and list gaps.

2. Scope by business risk.
   - Identify critical user flows and interfaces before enumerating cases.
   - Prioritize with `P0`, `P1`, `P2`, and `P3`.
   - Do not give every endpoint equal weight unless the user explicitly asks for exhaustive coverage.

3. Choose the output type.
   - If the caller provides a structured output schema, obey that schema exactly and do not add Markdown wrappers, extra prose, or fields outside the schema.
   - If the task is this repo's API automation generation flow, follow the configured `ApiAutomationGenerationResult` / `ApiGeneratedCase` contract.
   - For ad hoc human-readable planning only, include case id, priority, preconditions, request, expected response, data setup, cleanup, and automation note.
   - For automation advice, follow the existing project stack instead of introducing Postman, Newman, SuperTest, Rest Assured, or pytest unless the repo or user points there.

4. Cover the right API risks.
   - Functional success paths.
   - Parameter validation and boundary values.
   - Authentication and authorization.
   - Request and response contract.
   - Error status codes and error body consistency.
   - Idempotency and duplicate submission.
   - Data consistency, persistence, and cleanup.
   - Upstream/downstream integration.
   - Pagination, filtering, sorting, and search semantics.
   - File upload/download, streaming, webhook, async, or real-time behavior when relevant.
   - Minimal performance and stability checks for critical paths.

5. Verify or state limits.
   - If asked to implement tests, run the smallest meaningful verification first, such as test collection, focused test execution, schema parsing, or a direct request against a known local service.
   - If the target environment is unavailable, state what could not be verified and keep proposed cases tied to confirmed contracts.

## Protocol Guidance

- REST: focus on method semantics, status codes, request/response schema, resource lifecycle, idempotency, pagination/filtering/sorting, and auth.
- GraphQL: focus on query/mutation shape, variables, partial errors, nullability, authorization at field and resolver level, pagination, and N+1/performance risks.
- gRPC: focus on proto contract, status codes, metadata/auth, deadline/timeout behavior, streaming semantics, and backward compatibility.
- SOAP: focus on WSDL contract, envelope structure, namespaces, fault handling, and schema validation.
- WebSocket or streaming APIs: focus on connection lifecycle, auth, subscription setup, message ordering, reconnect behavior, heartbeat, and backpressure.

## Output Rules

- Be concrete. Do not write only "test normal and abnormal cases"; name the actual normal, abnormal, and boundary scenarios.
- Do not invent endpoints, fields, limits, roles, states, or business rules.
- Preserve the project's architecture and test stack.
- Treat external example skills and templates as inspiration only; do not copy licensed content into the project unless the user explicitly asks and license obligations are handled.
- Keep no-op or low-risk endpoints out of P0 unless they block a critical flow.
