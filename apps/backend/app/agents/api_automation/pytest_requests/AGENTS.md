# Pytest Requests Suite Instructions

You are operating inside the root of one business project's pytest + requests suite.

## Rules

- Inspect the existing suite before editing it.
- Keep one suite per business project.
- Preserve files for endpoints not selected in the current generation request.
- Create or repair shared files before generating endpoint test files.
- Keep each endpoint's test module and adjacent data file together.
- Treat backend-provided `artifacts.directory`, `artifacts.test_file`, and `artifacts.data_file` as mandatory targets.
- Do not replace backend-provided endpoint targets with inferred names such as `test_agent.py` or `test_v1.py`.
- Use runtime environment variables for base URLs, authentication, secrets, and file paths.
- Never write credentials, cookies, tokens, or host-machine absolute paths into generated source files.
- Run `pytest --collect-only` after edits; collection must not send real API requests.
- If collection fails, read the traceback and the affected files, repair the suite, and retry within the configured limit.
- Do not create another pytest project or another suite directory.

## Required Shared Files

The suite must contain the shared files listed by the backend suite contract, including:

- `pytest.ini`
- `pyproject.toml`
- `conftest.py`
- `api/client.py`
- `utils/data_loader.py`
- `utils/assertions.py`
- `utils/assert_utils.py`
