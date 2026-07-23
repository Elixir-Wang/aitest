from pathlib import Path

import pytest

from app.agents.api_automation.self_healing.validation import validate_workspace_path


@pytest.mark.parametrize("candidate", ["../outside.py", "D:/outside.py", ".git/config", "runtime/secret.txt"])
def test_workspace_path_rejects_unsafe_paths(tmp_path: Path, candidate: str) -> None:
    with pytest.raises(ValueError):
        validate_workspace_path(tmp_path, candidate)


def test_workspace_path_accepts_relative_suite_file(tmp_path: Path) -> None:
    assert validate_workspace_path(tmp_path, "utils/assertions.py") == (tmp_path / "utils/assertions.py").resolve()
