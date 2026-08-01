import asyncio
from pathlib import Path

import pytest
import yaml

from app.agents.page_exploration.tools import check_explored_url_tool, get_local_tools
from app.agents.page_exploration.tools.runtime_context import (
    PageExplorationRuntimeError,
    exploration_runtime_context,
    require_exploration_runtime,
)


def test_check_explored_url_tool_does_not_accept_runtime_identity() -> None:
    properties = check_explored_url_tool.get_input_schema().model_json_schema()["properties"]

    assert set(properties) == {"normalized_path"}


def test_page_exploration_agent_has_no_state_write_tool() -> None:
    tool_names = {tool.name for tool in get_local_tools()}

    assert "update_explored_url_tool" not in tool_names


def test_check_explored_url_tool_uses_bound_project_and_storage_root(tmp_path: Path) -> None:
    page_path = tmp_path / "project-real" / "page_exploration" / "pages" / "page-home.yaml"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "4.0",
                "page": {"id": "page-home", "normalized_path": "/home"},
                "states": [{"id": "home.root"}],
                "elements": [],
                "transitions": [],
                "quality": {"status": "partial", "unresolved": []},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with exploration_runtime_context(
        project_id="project-real",
        run_id="exp-real",
        storage_root=tmp_path,
    ):
        result = check_explored_url_tool.invoke({"normalized_path": "/home"})

    assert result["page_id"] == "page-home"
    assert result["explored"] is False


def test_page_exploration_tools_require_bound_runtime_identity() -> None:
    with pytest.raises(PageExplorationRuntimeError, match="runtime is not bound"):
        check_explored_url_tool.invoke({"normalized_path": "/home"})


def test_exploration_runtime_context_resets_after_exit(tmp_path: Path) -> None:
    with exploration_runtime_context(
        project_id="project-real",
        run_id="exp-real",
        storage_root=tmp_path,
    ):
        runtime = require_exploration_runtime()
        assert runtime.project_id == "project-real"
        assert runtime.run_id == "exp-real"
        assert runtime.storage_root == tmp_path

    with pytest.raises(PageExplorationRuntimeError, match="runtime is not bound"):
        require_exploration_runtime()


def test_exploration_runtime_context_is_isolated_between_async_tasks(tmp_path: Path) -> None:
    async def read_runtime(project_id: str, run_id: str) -> tuple[str, str]:
        with exploration_runtime_context(
            project_id=project_id,
            run_id=run_id,
            storage_root=tmp_path,
        ):
            await asyncio.sleep(0)
            runtime = require_exploration_runtime()
            return runtime.project_id, runtime.run_id

    async def run() -> list[tuple[str, str]]:
        return await asyncio.gather(
            read_runtime("project-a", "exp-a"),
            read_runtime("project-b", "exp-b"),
        )

    assert asyncio.run(run()) == [("project-a", "exp-a"), ("project-b", "exp-b")]
