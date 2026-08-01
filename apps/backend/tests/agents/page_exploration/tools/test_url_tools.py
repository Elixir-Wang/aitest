from pathlib import Path

import yaml

from app.agents.page_exploration.tools.url_tools import check_explored_url
from app.services.page_exploration.coverage_registry import update_coverage


def _write_page(tmp_path: Path, *, schema_version: str = "4.0") -> None:
    page_yaml = tmp_path / "proj-x" / "page_exploration" / "pages" / "page-x.yaml"
    page_yaml.parent.mkdir(parents=True, exist_ok=True)
    page_yaml.write_text(
        yaml.safe_dump(
            {
                "schema_version": schema_version,
                "page": {"id": "page-x", "normalized_path": "/x"},
                "states": [{"id": "x.root"}, {"id": "x.dialog"}],
                "elements": [],
                "transitions": [],
                "quality": {"status": "partial", "unresolved": []},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_unexplored_url_returns_empty_schema_4_coverage_summary(tmp_path: Path) -> None:
    result = check_explored_url(
        normalized_path="/workspace",
        project_id="proj-x",
        base_dir=tmp_path,
    )

    assert result == {
        "explored": False,
        "page_id": "",
        "page_completed": False,
        "completed_states": 0,
        "completed_operations": 0,
        "pending_operations": 0,
    }


def test_schema_4_page_uses_shared_coverage(tmp_path: Path) -> None:
    _write_page(tmp_path)
    update_coverage(
        tmp_path,
        "proj-x",
        run_id="run-1",
        mode="loop",
        pages=[{"page_id": "page-x", "path": "/x", "status": "complete", "states": ["x.root"]}],
        completed_actions=[
            {"page_id": "page-x", "element_key": "button-create", "action": "click"},
        ],
        collection_groups=[],
    )

    result = check_explored_url(
        normalized_path="/x",
        project_id="proj-x",
        base_dir=tmp_path,
    )

    assert result == {
        "explored": True,
        "page_id": "page-x",
        "page_completed": True,
        "completed_states": 1,
        "completed_operations": 1,
        "pending_operations": 0,
    }


def test_force_reexplore_ignores_completed_shared_coverage(tmp_path: Path) -> None:
    _write_page(tmp_path)
    update_coverage(
        tmp_path,
        "proj-x",
        run_id="run-1",
        mode="autonomous",
        pages=[{"page_id": "page-x", "path": "/x", "status": "complete", "states": ["x.root"]}],
        completed_actions=[],
        collection_groups=[],
    )

    result = check_explored_url(
        normalized_path="/x",
        project_id="proj-x",
        base_dir=tmp_path,
        force_reexplore=True,
    )

    assert result["explored"] is False
    assert result["page_id"] == "page-x"
    assert result["page_completed"] is True


def test_legacy_page_is_not_read_by_runtime(tmp_path: Path) -> None:
    _write_page(tmp_path, schema_version="3.0")

    result = check_explored_url(
        normalized_path="/x",
        project_id="proj-x",
        base_dir=tmp_path,
    )

    assert result["explored"] is False
    assert result["page_id"] == ""
