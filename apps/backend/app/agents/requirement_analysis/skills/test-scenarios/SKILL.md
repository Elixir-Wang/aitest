---
name: test-scenarios
description: Probe requirements from a test execution perspective. Use to derive missing roles, preconditions, actions, expected outcomes, boundary values, exception paths, and acceptance criteria gaps from the primary requirement.
---

# Test Scenario Probe

Use test design as a probe, not as a final test-case generator.

For each important primary requirement, ask whether a tester can determine:

- Test objective: what behavior is being verified.
- User role: who performs the action and with what permission.
- Starting conditions: data, state, configuration, login status, project context, or dependencies.
- Test steps: the visible or API-level actions needed to exercise the behavior.
- Expected outcomes: observable result, data change, status change, message, audit log, notification, or generated artifact.
- Boundary values: min/max counts, thresholds, empty data, duplicates, invalid input, timeout, concurrency, or pagination.
- Exception paths: permission denied, validation failed, dependency unavailable, conflict, retry, cancel, rollback, or archived data.

If a scenario cannot be written from the primary requirement, record the missing information as an unresolved finding.
If a supporting document clearly answers the gap, it can be used as evidence for an auxiliary supplement.
Do not generate final QA test cases in this skill.
