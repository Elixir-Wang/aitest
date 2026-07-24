---
name: pytest-playwright-ui-generation
description: Generate or update one UI automation case in the owning business project's pytest Playwright suite.
---

# Workflow

1. Inspect the existing project suite and its `AGENTS.md`.
2. Read the backend-owned case data file and exploration evidence.
3. Reuse existing POM and shared helpers before adding code.
4. Normalize the derived data file when needed; keep secrets as environment references.
5. Produce a strict v1 AutomationPlan using only evidence-backed locators.
   - Copy declared `case.parameters` keys into `AutomationPlan.parameters`.
   - Use `click_parameter_text` with `value_ref` when a step selects the current parameter value.
   - Never replace a parameter reference with one concrete value.
   - After sending a chat message, use `wait_for_response` with an assistant-only response locator.
   - Do not use `wait_visible` for response completion or assume an initial welcome message exists.
6. Validate the plan, render it through the deterministic tool, and run pytest collection.

# Prohibitions

- Do not update the source test case.
- Keep every business project's files inside its backend-provided project namespace.
- Do not invent pages, routes, locators, expected results, or business rules.
- Do not choose output paths other than the backend-provided artifact paths.
- Do not write arbitrary Python instead of calling the renderer.
- Do not execute real UI tests during generation.
