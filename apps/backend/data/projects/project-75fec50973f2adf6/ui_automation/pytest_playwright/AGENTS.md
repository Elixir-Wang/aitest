# Pytest Playwright Suite Instructions

- Keep this suite scoped to its owning business project.
- Keep pages, tests, and data inside the backend-provided project namespace.
- Preserve files not selected by the current generation request.
- Only edit backend-provided artifact paths.
- Derived case data may be normalized, but secrets must remain environment references.
- Never invent locators; every locator requires exploration evidence.
- Preserve declared case parameters and reference their values instead of hard-coding one value.
- Run pytest collection after code changes and never execute real tests during generation.
