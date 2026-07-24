# Pytest Requests Suite Instructions

You are operating inside the root of one business project's pytest + requests suite.

## Virtual Path Contract

- The virtual filesystem root `/` is already the pytest_requests suite root.
- `/` is not the parent of the suite. Never create `/pytest_requests` or a nested `pytest_requests/pytest_requests` project.
- Every backend-provided `artifacts.*` path is relative to `/`. If a tool requires an absolute path, prefix the artifact path with `/` exactly once.
- For example, `testcases/example/post/test_api.py` maps to `/testcases/example/post/test_api.py`, never `/pytest_requests/testcases/example/post/test_api.py`.
- Never construct host paths such as `/Users/...` or `/home/...`. Do not use `cp`, `rsync`, `shutil`, or temporary scripts to copy files between virtual and host paths.
- Inspect `/` and `/AGENTS.md` directly. Keep every read and write inside `/`.

## Rules

- Inspect the existing suite before editing it.
- Keep one suite per business project.
- Preserve files for endpoints not selected in the current generation request.
- Create or repair shared files before generating endpoint test files.
- Keep each endpoint's test module and adjacent data file together.
- Treat backend-provided `artifacts.directory`, `artifacts.test_file`, and `artifacts.data_file` as mandatory targets.
- Treat `artifacts.data_file` as a read-only database snapshot. Never rewrite, append, wrap, rename fields, or duplicate its cases.
- Only create or update `artifacts.test_file` for a selected endpoint, reusing existing test and shared code where possible.
- Do not replace backend-provided endpoint targets with inferred names such as `test_agent.py` or `test_v1.py`.
- Use runtime environment variables for base URLs, authentication, secrets, and file paths.
- Never write credentials, cookies, tokens, or host-machine absolute paths into generated source files.
- Run `pytest --collect-only` after edits; collection must not send real API requests.
- If collection fails, read the traceback and the affected files, repair the suite, and retry within the configured limit.
- Do not create another pytest project or another suite directory.

## Required Shared Files

The suite must contain the shared files listed by the backend suite contract, including:

- `pytest.ini`
- `conftest.py`
- `api/client.py`
- `utils/data_loader.py`
- `utils/assertions.py`
- `utils/assert_utils.py`
