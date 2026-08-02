from __future__ import annotations

from pathlib import Path
from pathlib import PureWindowsPath


FORBIDDEN_ROOTS = {".git", "runtime", ".pytest_cache", "__pycache__"}


def validate_workspace_path(workspace: Path, candidate: str) -> Path:
    raw = Path(candidate)
    windows_raw = PureWindowsPath(candidate)
    if raw.is_absolute() or windows_raw.is_absolute() or windows_raw.drive or ".." in raw.parts or not raw.parts:
        raise ValueError("修复路径必须是 workspace 内的相对路径。")
    if raw.parts[0].lower() in FORBIDDEN_ROOTS:
        raise ValueError("修复路径属于禁止目录。")
    root = workspace.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("修复路径越界。") from exc
    return resolved
