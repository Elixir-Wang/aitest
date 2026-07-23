# Pytest Playwright Suite Instructions

- Keep one shared suite for the whole platform.
- Keep each business project's pages, tests, and data inside its backend-provided project namespace.
- Preserve files not selected by the current generation request.
- Only edit backend-provided artifact paths.
- Derived case data may be normalized, but secrets must remain environment references.
- Never invent locators; every locator requires exploration evidence.
- Run pytest collection after code changes and never execute real tests during generation.
