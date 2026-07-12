# Pytest and Requests best practices

## Pytest

- Put reusable fixtures in project-level `conftest.py` and give expensive shared clients session scope.
- Use `pytest.mark.parametrize` so every API case is an independently collected test with its own failure and report entry.
- Keep fixture dependencies explicit and avoid hidden global mutable state.
- Use stable readable parameter IDs derived from case titles or IDs.
- Configure test discovery in `pytest.ini` and verify generated projects with `pytest --collect-only` before execution.

Official references:

- https://docs.pytest.org/en/stable/how-to/fixtures.html
- https://docs.pytest.org/en/stable/how-to/parametrize.html
- https://docs.pytest.org/en/stable/reference/customize.html

## Requests

- Reuse one `requests.Session` for default headers, authentication, cookies, and connection pooling.
- Set an explicit timeout on every request. Requests has no default timeout.
- Keep TLS verification enabled by default; make disabling it an explicit environment setting.
- Use `params` for query values, `json` for JSON bodies, `data` plus `files` for multipart requests.
- Close file handles deterministically and never log secrets.
- Use response-level assertions that preserve useful failure context.

Official references:

- https://requests.readthedocs.io/en/latest/user/advanced/
- https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts
- https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification

## Dependency policy

Start with `pytest`, `requests`, and the repository's existing reporting plugin. Add schema, retry, faker, or parallel-execution dependencies only when a verified requirement needs them.
