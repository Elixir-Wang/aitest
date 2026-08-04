# SSE Timing Semantics Design

## Goal

Make SSE timing metrics match the confirmed business meaning without adding an implicit `query_end` metric.

## Confirmed Semantics

- `call_llm 开始时间`: request start to the first SSE event whose `$.data.event_type` equals `call_llm_start`.
- `首次有效内容时间`: request start to the first SSE event whose `$.data.answer` is non-empty.
- `LLM 启动到首次有效内容`: paired per-request delta between the two metrics above.
- The HTTP SSE request duration is connection/response-header latency, not stream completion latency.

## Design

- Reuse the existing generic `non_empty` matcher for `$.data.answer`; do not add a special-case parser.
- Detect the two confirmed metric roles from their match rules and calculate the paired delta in each measurement.
- Aggregate the paired delta as a derived SSE metric without modifying the stored user metric configuration.
- Mark streaming HTTP request rows with connection-latency semantics for the frontend.
- Bound displayed SSE metric attempts to completed HTTP SSE requests so manual-stop report snapshots do not show an extra metric attempt.
- Preserve configured metrics only; do not create or listen for `query_end`.

## Acceptance

- Empty `answer` events do not satisfy first-content timing.
- Paired delta is calculated from the same request and is never inferred by subtracting percentiles.
- SSE HTTP rows are visibly labeled as connection latency.
- Manual-stop snapshots do not display more SSE metric attempts than completed SSE HTTP requests.

