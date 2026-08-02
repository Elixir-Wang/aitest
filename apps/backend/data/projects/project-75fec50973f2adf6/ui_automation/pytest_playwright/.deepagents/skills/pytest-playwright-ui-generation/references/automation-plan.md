# AutomationPlan v1

The plan maps one source test case to page objects, ordered steps, assertions, and backend-owned artifact paths. Every step keeps `source_step_id`; every assertion keeps `source_expected_result_id`; every locator contains non-empty `evidence_refs`.

Every new step must also set `business_step_id` to an actual source case step ID and set `title` to the source step's readable action. When one business step needs multiple operations, each operation keeps a unique `source_step_id` but shares the same `business_step_id` and `title`. Set `visible: false` only for internal cleanup operations that should remain auditable but hidden in the default result view.

Set an assertion's `after_step_id` to the `source_step_id` whose result it validates. This keeps response and navigation assertions next to the action they describe. Only omit `after_step_id` when the assertion intentionally validates the final state of the whole case.

Use `wait_for_response` immediately after the `click` or `press` that sends a chat message. Its element must locate assistant responses only. The renderer snapshots the current response before sending and waits for a new, stable response, so the flow must not depend on a welcome message.

Use `commit_value` for an input whose visible auto-populated value must be re-entered to update frontend form state. It reads and refills the current value; if the platform leaves it blank, the renderer supplies a unique release value, so generated tests do not hardcode a version that becomes stale after publishing.
