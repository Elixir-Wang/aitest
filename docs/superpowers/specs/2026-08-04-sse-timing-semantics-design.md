# SSE Timing Semantics Design

## Goal

Make SSE timing metrics match the confirmed business meaning without adding an implicit `query_end` metric.

## Confirmed Semantics

- `call_llm 开始时间`: request start to the first SSE event whose `$.data.event_type` equals `call_llm_start`.
- `首次有效内容时间`: request start to the first SSE event whose `$.data.index` equals `0`, matching the confirmed reference client.
- When both metrics are configured, first content is eligible only after the same request has observed `call_llm_start`.
- An interval metric is calculated only when its configured timing uses `start: metric_matched` and references another configured metric; it is never emitted implicitly.
- The HTTP SSE request duration is connection/response-header latency, not stream completion latency.

## Design

- Reuse the existing generic `equals` matcher for `$.data.index`; do not add a special-case parser.
- Upgrade the known legacy first-output rules to the confirmed `$.data.index == 0` matcher without modifying stored configuration.
- Re-render every run from the validated structured plan with the current runtime so reruns cannot execute stale generated helpers.
- Treat the configured run duration as the load-generation window. At its deadline, Locust stops starting new scenario iterations and gives each in-flight iteration enough time to finish all remaining sequential steps.
- Calculate `--stop-timeout` from the structured scenario budget: sum request timeouts and waits, use the larger of request timeout and SSE stream limit, then add a five-second scheduling buffer.
- Use the same graceful timeout for manual stops; send `SIGTERM` first and force-kill only if Locust exceeds the calculated drain window.
- Mark streaming HTTP request rows with connection-latency semantics for the frontend.
- Bound displayed SSE metric attempts to completed HTTP SSE requests so manual-stop report snapshots do not show an extra metric attempt.
- Preserve configured metrics only; do not create or listen for `query_end`.
- Allow an SSE request to run with no event metrics. AI discovery returns suggestions only; a suggestion becomes active only after a user saves it.

## Acceptance

- Events before `index == 0` do not satisfy first-content timing even if they contain a non-empty `answer`.
- No implicit derived metric row is added beyond the configured SSE metrics.
- A two-request scenario reports equal endpoint counts after normal completion unless an in-flight scenario exceeds its configured timeout budget.
- SSE HTTP rows are visibly labeled as connection latency.
- Manual-stop snapshots do not display more SSE metric attempts than completed SSE HTTP requests.
