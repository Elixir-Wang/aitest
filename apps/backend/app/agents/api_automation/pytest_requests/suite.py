from __future__ import annotations

import re
import shutil
from pathlib import Path


BUILTIN_SKILL_ROOT = Path(__file__).parent / "skills"
SUPPORTED_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


REQUIRED_SUITE_FILES = (
    "AGENTS.md",
    "pytest.ini",
    "pyproject.toml",
    "conftest.py",
    "api/__init__.py",
    "api/client.py",
    "testcases/__init__.py",
    "testcases/conftest.py",
    "utils/__init__.py",
    "utils/data_loader.py",
    "utils/assertions.py",
    "utils/assert_utils.py",
    "support/__init__.py",
    "config/__init__.py",
    "data/__init__.py",
)


def ensure_suite_root(suite_path: Path) -> Path:
    resolved = suite_path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    skill_target = resolved / ".deepagents" / "skills" / "pytest-requests-code-generation"
    skill_target.parent.mkdir(parents=True, exist_ok=True)
    if BUILTIN_SKILL_ROOT.exists():
        shutil.copytree(
            BUILTIN_SKILL_ROOT / "pytest-requests-code-generation",
            skill_target,
            dirs_exist_ok=True,
        )
    return resolved


def suite_missing_files(suite_path: Path) -> list[str]:
    root = suite_path.resolve()
    return [relative_path for relative_path in REQUIRED_SUITE_FILES if not (root / relative_path).is_file()]


def suite_is_initialized(suite_path: Path) -> bool:
    return not suite_missing_files(suite_path)


def endpoint_artifact_paths(endpoint: dict) -> tuple[str, str, str]:
    method = str(endpoint.get("method", "")).strip().lower()
    if method not in SUPPORTED_HTTP_METHODS:
        raise ValueError(f"Unsupported HTTP method: {method or '<empty>'}")

    raw_path = str(endpoint.get("normalized_path") or endpoint.get("path") or "")
    path_parts = [part for part in raw_path.strip("/").split("/") if part]
    normalized_parts = [_normalize_path_segment(part) for part in path_parts]
    endpoint_dir = "/".join(["testcases", *(normalized_parts or ["root"]), method])
    return endpoint_dir, f"{endpoint_dir}/test_api.py", f"{endpoint_dir}/cases.yaml"


def _normalize_path_segment(value: str) -> str:
    if value in {".", ".."}:
        raise ValueError(f"Unsafe endpoint path segment: {value}")
    if "{" in value or "}" in value:
        match = re.fullmatch(r"\{([^{}]+)\}", value)
        if not match:
            raise ValueError(f"Invalid endpoint path parameter segment: {value}")
        parameter_name = _slugify(match.group(1))
        if parameter_name == "generated":
            raise ValueError(f"Invalid endpoint path parameter segment: {value}")
        return f"by_{parameter_name}"
    return _slugify(value)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "generated"
