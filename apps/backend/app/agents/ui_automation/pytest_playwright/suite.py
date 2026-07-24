from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.core import settings


BUILTIN_SKILL_ROOT = Path(__file__).parent / "skills" / "pytest-playwright-ui-generation"


def project_suite_path(project_id: str) -> Path:
    return settings.PROJECT_FILE_STORAGE_ROOT / project_id / "ui_automation" / "pytest_playwright"


def legacy_shared_suite_path() -> Path:
    return settings.PROJECT_FILE_STORAGE_ROOT.parent / "ui_automation" / "pytest_playwright"


def ensure_suite_root(suite_path: Path) -> Path:
    resolved = suite_path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    skill_target = resolved / ".deepagents" / "skills" / "pytest-playwright-ui-generation"
    if BUILTIN_SKILL_ROOT.exists():
        skill_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BUILTIN_SKILL_ROOT, skill_target, dirs_exist_ok=True)
    return resolved


def resolve_suite_file(suite_path: Path, relative_path: str) -> Path:
    root = suite_path.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("目标文件必须位于 pytest_playwright 工程目录内。") from exc
    return candidate


def relative_suite_path(suite_path: Path, path: Path) -> str:
    root = suite_path.resolve()
    candidate = path.resolve()
    try:
        return candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("目标文件必须位于 pytest_playwright 工程目录内。") from exc


def case_artifact_paths(
    suite_path: Path,
    *,
    project_id: str,
    automation_case_id: str,
    source_test_case_id: str,
    title: str,
) -> dict[str, Path]:
    project_key = _slugify(project_id)
    key = _slugify(f"{title}_{source_test_case_id}_{automation_case_id}")
    return {
        "test_file": resolve_suite_file(suite_path, f"testcases/generated/{project_key}/test_{key}.py"),
        "data_file": resolve_suite_file(suite_path, f"data/projects/{project_key}/cases/{key}.yaml"),
        "plan_file": resolve_suite_file(suite_path, f"data/projects/{project_key}/cases/{key}.plan.json"),
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "generated_case"


__all__ = [
    "case_artifact_paths",
    "ensure_suite_root",
    "legacy_shared_suite_path",
    "project_suite_path",
    "relative_suite_path",
    "resolve_suite_file",
]
