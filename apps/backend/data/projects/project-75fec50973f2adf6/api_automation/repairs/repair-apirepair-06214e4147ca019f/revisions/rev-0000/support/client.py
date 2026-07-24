import os
import re
from pathlib import Path
from urllib.parse import quote

import requests

from support.auth import build_auth_headers


class ApiClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(build_auth_headers())

    @classmethod
    def from_environment(cls):
        base_url = os.environ.get("API_BASE_URL", "")
        if not base_url:
            raise RuntimeError("API_BASE_URL is required.")
        timeout = int(os.environ.get("API_TIMEOUT_SECONDS", "30"))
        return cls(base_url=base_url, timeout=timeout)

    def request(self, request_data: dict, test_data: dict | None = None):
        method = request_data.get("method", "GET")
        path = _expand_path(request_data.get("path", ""), test_data or {})
        url = f"{self.base_url}{path}"
        query = _expand_environment(request_data.get("query") or {})
        headers = _expand_environment(request_data.get("headers") or {})
        body = _expand_environment(request_data.get("body")) if "body" in request_data else None
        files, handles = _build_files(request_data.get("files") or {})
        try:
            return self.session.request(
                method,
                url,
                params=query or None,
                data=body if files else None,
                json=None if files else body,
                files=files or None,
                headers=headers or None,
                timeout=self.timeout,
            )
        finally:
            for handle in handles:
                handle.close()


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PATH_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_path(path: str, test_data: dict) -> str:
    values = {
        key: value.get("value") if isinstance(value, dict) and "value" in value else value
        for key, value in test_data.items()
    }
    expanded = _expand_environment(path)
    return _PATH_PATTERN.sub(
        lambda match: quote(str(_expand_environment(values.get(match.group(1), match.group(0)))), safe=""),
        expanded,
    )


def _expand_environment(value):
    if isinstance(value, dict):
        return {key: _expand_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment(item) for item in value]
    if not isinstance(value, str):
        return value
    full_match = _ENV_PATTERN.fullmatch(value)
    if full_match:
        return os.environ.get(full_match.group(1), "")
    return _ENV_PATTERN.sub(lambda match: os.environ.get(match.group(1), ""), value)


def _build_files(file_specs: dict):
    files = []
    handles = []
    try:
        for field_name, raw_specs in file_specs.items():
            specs = raw_specs if isinstance(raw_specs, list) else [raw_specs]
            for raw_spec in specs:
                spec = raw_spec if isinstance(raw_spec, dict) else {"path": raw_spec}
                file_path = Path(_expand_environment(spec.get("path", ""))).expanduser()
                if not str(file_path) or not file_path.is_file():
                    raise RuntimeError(f"Upload file does not exist for field {field_name}: {file_path}")
                handle = file_path.open("rb")
                handles.append(handle)
                filename = _expand_environment(spec.get("filename")) or file_path.name
                content_type = _expand_environment(spec.get("content_type")) or "application/octet-stream"
                files.append((field_name, (filename, handle, content_type)))
        return files, handles
    except Exception:
        for handle in handles:
            handle.close()
        raise
