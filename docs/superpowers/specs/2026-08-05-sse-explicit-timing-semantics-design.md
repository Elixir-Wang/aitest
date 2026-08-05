# SSE Explicit Timing Semantics Design

## Goal

Make every SSE performance metric explicitly identify its source request, timing start, timing end, and calculation formula so AI suggestions, user confirmation, generated Locust scripts, aggregation, and result presentation use the same semantics.

## Confirmed Semantics

- SSE connection latency: `02 POST /openapi/v1/gw/multi-agent/sse` request start to HTTP response headers.
- `call_llm 开始时间`: the same SSE request start to the first matching `call_llm_start` frame.
- `首次有效内容时间`: the same SSE request start to the confirmed first-content frame.
- `LLM 首内容等待时间`: first-content elapsed time minus `call_llm_start` elapsed time from the same request.
- Scenario step `01 POST /openapi/v1/gw/multi-agent/segment-code/gen` must never be used as the timing origin for SSE business metrics.

## Data Model

Each persisted SSE metric carries a category and request-relative timing declaration. Existing configurations remain valid through deterministic defaults.

```json
{
  "id": "llm_start",
  "name": "call_llm 开始时间",
  "category": "milestone_start",
  "timing": {
    "scope": "request",
    "start": "request_started",
    "source_request_id": "step_sse_chat"
  },
  "match": {
    "source": "data_json",
    "path": "$.data.event_type",
    "operator": "equals",
    "expected": "call_llm_start"
  }
}
```

Derived metrics are not independently matched. The runtime calculates them only when both source metrics exist and their order is valid.

## AI And Confirmation

- Candidate generation attaches category, source request ID/name, timing origin, and a human-readable formula.
- The confirmation dialog displays the exact source interface, start point, end condition, dependency, and formula.
- AI uncertainty remains visible and the user must apply a validated draft before the metric becomes active.
- Structural fallback remains authoritative when AI output is invalid.

## Runtime

- Start the request clock immediately before the configured SSE request.
- Capture connection latency when the streaming response context opens.
- Record first-match event elapsed times relative to that request clock.
- Gate first-output metrics on an observed `call_llm_start` when such a metric is configured.
- Calculate `derived:llm_start_to_first_content` as `first_output - llm_start`; reject negative ordering.
- Persist source request metadata and timing semantics in each measurement.

## Aggregation And Presentation

- Aggregate matched and derived values independently from Locust HTTP statistics.
- Keep the HTTP request row labelled as SSE connection latency.
- Display source interface and formula for SSE business rows.
- Limit measurement aggregation to Locust-completed SSE requests to keep sample counts aligned.

## Compatibility

- Legacy first-output rules using `event_type == answer` or non-empty `answer` normalize to the confirmed `$.data.index == 0` rule.
- Legacy metrics without category/timing receive deterministic defaults during validation and rendering.
- Historical run artifacts are not rewritten; new runs are rendered from the current validated plan.

## Verification

- Schema tests cover defaults, invalid source request IDs, dependencies, and derived timing declarations.
- Runtime tests cover request-relative timing, connection latency, event gating, derived values, and invalid order.
- API tests cover source-interface/formula metadata in result rows.
- Frontend contract tests cover confirmation and result semantics copy.
