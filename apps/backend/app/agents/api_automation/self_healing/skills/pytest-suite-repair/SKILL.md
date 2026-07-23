---
name: pytest-suite-repair
description: Repair a pytest requests suite inside a temporary workspace and validate the candidate.
---

# Pytest Suite Repair

- Inspect existing code and data before editing.
- Keep all changes inside the current workspace.
- Preserve test intent and coverage.
- Never use skip, xfail, swallowed exceptions, or weakened assertions to create passing results.
- Validate collection and the complete suite after changes.
- Record database-owned case changes as structured `case_updates` in `.repair-result.json`.
