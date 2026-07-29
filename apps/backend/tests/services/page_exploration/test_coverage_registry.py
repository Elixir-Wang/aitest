from pathlib import Path

import yaml

from app.services.page_exploration.coverage_registry import (
    build_autonomous_coverage_summary,
    build_coverage_view,
    clear_page_coverage,
    coverage_updates_from_artifacts,
    is_action_completed,
    is_collection_group_completed,
    is_page_complete,
    is_state_completed,
    load_coverage,
    update_coverage,
)


def test_load_coverage_returns_empty_contract_when_file_is_missing(tmp_path: Path) -> None:
    coverage = load_coverage(tmp_path, "project-1")

    assert coverage == {"schema_version": "1.0", "pages": {}}


def test_update_coverage_persists_completed_states_actions_and_collection_groups(tmp_path: Path) -> None:
    coverage = update_coverage(
        tmp_path,
        "project-1",
        run_id="run-loop",
        mode="loop",
        pages=[
            {
                "page_id": "page-workspace",
                "path": "/workspace",
                "artifact": "pages/page-workspace.yaml",
                "status": "partial",
                "states": ["workspace.root"],
            }
        ],
        completed_actions=[
            {
                "page_id": "page-workspace",
                "element_key": "workspace.create_agent_trigger",
                "action": "click",
                "from_state": "workspace.root",
                "to_state": "workspace.create_agent_popover",
            }
        ],
        collection_groups=[
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "自主规划Agent:已发布",
                "representative": "tmp",
                "status": "completed",
            }
        ],
    )

    assert is_page_complete(coverage, "page-workspace") is False
    assert is_state_completed(coverage, "page-workspace", "workspace.root") is True
    assert is_action_completed(
        coverage,
        "page-workspace",
        "workspace.create_agent_trigger",
        "click",
    ) is True
    assert is_collection_group_completed(
        coverage,
        "page-workspace",
        "workspace.agent_cards",
        "自主规划Agent:已发布",
    ) is True

    stored = yaml.safe_load(
        (
            tmp_path
            / "project-1"
            / "page_exploration"
            / "exploration-coverage.yaml"
        ).read_text(encoding="utf-8")
    )
    assert stored == coverage


def test_pending_update_does_not_downgrade_completed_collection_group(tmp_path: Path) -> None:
    update_coverage(
        tmp_path,
        "project-1",
        run_id="run-1",
        mode="autonomous",
        pages=[],
        completed_actions=[],
        collection_groups=[
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "Multi-Agent:草稿",
                "representative": "test",
                "status": "completed",
            }
        ],
    )

    coverage = update_coverage(
        tmp_path,
        "project-1",
        run_id="run-2",
        mode="loop",
        pages=[],
        completed_actions=[],
        collection_groups=[
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "Multi-Agent:草稿",
                "status": "pending",
            }
        ],
    )

    group = coverage["pages"]["page-workspace"]["collections"]["workspace.agent_cards"]["groups"][
        "Multi-Agent:草稿"
    ]
    assert group["status"] == "completed"
    assert group["run_id"] == "run-1"


def test_autonomous_summary_contains_only_compact_completed_and_pending_refs(tmp_path: Path) -> None:
    coverage = update_coverage(
        tmp_path,
        "project-1",
        run_id="run-1",
        mode="loop",
        pages=[
            {
                "page_id": "page-workspace",
                "path": "/workspace",
                "artifact": "pages/page-workspace.yaml",
                "status": "complete",
                "states": ["workspace.root"],
            }
        ],
        completed_actions=[
            {
                "page_id": "page-workspace",
                "element_key": "workspace.create_agent_trigger",
                "action": "click",
            }
        ],
        collection_groups=[
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "自主规划Agent:已发布",
                "status": "completed",
            },
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "写作Agent:草稿",
                "status": "pending",
            },
        ],
    )

    summary = build_autonomous_coverage_summary(coverage)

    assert summary == {
        "completed_pages": ["page-workspace"],
        "completed_states": ["workspace.root"],
        "completed_actions": ["workspace.create_agent_trigger:click"],
        "completed_collection_groups": [
            {
                "collection": "workspace.agent_cards",
                "type": "自主规划Agent",
                "status": "已发布",
            }
        ],
        "pending_collection_groups": [
            {
                "collection": "workspace.agent_cards",
                "type": "写作Agent",
                "status": "草稿",
            }
        ],
    }


def test_coverage_view_merges_durable_coverage_with_resumable_checkpoint() -> None:
    coverage = {
        "schema_version": "1.0",
        "pages": {
            "page-home": {
                "path": "/home",
                "status": "partial",
                "states": {"state-home": {"status": "completed"}},
                "actions": {
                    "button-done:click": {"status": "completed", "run_id": "run-1"},
                },
            }
        },
    }
    checkpoint = {
        "run_id": "run-1",
        "project_id": "project-1",
        "current_state_key": "state-home",
        "visited_states": {
            "state-home": {"page_key": "page-home", "url": "https://example.test/home"},
        },
        "frontier": [
            {
                "state_key": "state-home",
                "page_key": "page-home",
                "element_key": "button-done",
                "action_type": "click",
                "status": "verified",
            },
            {
                "state_key": "state-home",
                "page_key": "page-home",
                "element_key": "button-next",
                "action_type": "click",
                "status": "pending",
            },
            {
                "state_key": "state-home",
                "page_key": "page-home",
                "element_key": "button-risky",
                "action_type": "click",
                "status": "blocked",
            },
        ],
    }

    view = build_coverage_view(coverage, checkpoint=checkpoint)

    assert view["summary"] == {
        "pages_discovered": 1,
        "pages_completed": 0,
        "states_discovered": 1,
        "states_completed": 1,
        "actions_discovered": 3,
        "actions_completed": 1,
        "actions_pending": 1,
        "actions_blocked": 1,
        "actions_failed": 0,
    }
    assert view["resume"] == {
        "available": True,
        "run_id": "run-1",
        "state_key": "state-home",
        "page_id": "page-home",
        "next_action": {
            "element_key": "button-next",
            "action_type": "click",
            "state_key": "state-home",
            "page_id": "page-home",
        },
    }
    assert [action["status"] for action in view["pages"][0]["actions"]] == [
        "completed",
        "pending",
        "blocked",
    ]


def test_clear_page_coverage_removes_only_requested_page(tmp_path: Path) -> None:
    update_coverage(
        tmp_path,
        "project-1",
        run_id="run-1",
        mode="loop",
        pages=[
            {"page_id": "page-workspace", "status": "complete"},
            {"page_id": "page-editor", "status": "complete"},
        ],
        completed_actions=[],
        collection_groups=[],
    )

    clear_page_coverage(tmp_path, "project-1", "page-workspace")

    coverage = load_coverage(tmp_path, "project-1")
    assert set(coverage["pages"]) == {"page-editor"}


def test_coverage_updates_from_schema_4_artifacts(tmp_path: Path) -> None:
    pages_dir = tmp_path / "project-1" / "page_exploration" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page-workspace.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "4.0",
                "page": {
                    "id": "page-workspace",
                    "normalized_path": "/workspace",
                },
                "states": [
                    {"id": "workspace.root", "type": "root"},
                    {"id": "workspace.popover", "type": "popover"},
                ],
                "elements": [],
                "collections": [
                    {
                        "key": "workspace.agent_cards",
                        "groups": [
                            {
                                "key": "自主规划 Agent:已发布",
                                "representative": "tmp",
                                "actions": ["分析", "使用"],
                            }
                        ],
                    }
                ],
                "transitions": [
                    {
                        "from_state": "workspace.root",
                        "action": "click",
                        "target": "button-create",
                        "to_state": "workspace.popover",
                    }
                ],
                "quality": {"status": "complete", "unresolved": []},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updates = coverage_updates_from_artifacts(tmp_path, "project-1")

    assert updates == {
        "pages": [
            {
                "page_id": "page-workspace",
                "path": "/workspace",
                "artifact": "pages/page-workspace.yaml",
                "status": "complete",
                "states": ["workspace.root", "workspace.popover"],
            }
        ],
        "completed_actions": [
            {
                "page_id": "page-workspace",
                "element_key": "button-create",
                "action": "click",
                "from_state": "workspace.root",
                "to_state": "workspace.popover",
            }
        ],
        "collection_groups": [
            {
                "page_id": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "group_key": "自主规划 Agent:已发布",
                "representative": "tmp",
                "status": "pending",
            }
        ],
    }


def test_coverage_updates_ignore_legacy_and_unresolved_artifacts(tmp_path: Path) -> None:
    pages_dir = tmp_path / "project-1" / "page_exploration" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "legacy.yaml").write_text("schema_version: '3.0'\n", encoding="utf-8")
    (pages_dir / "pages-index.yaml").write_text("pages: []\n", encoding="utf-8")
    (pages_dir / "page-partial.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "4.0",
                "page": {"id": "page-partial", "normalized_path": "/partial"},
                "states": [{"id": "partial.root"}],
                "transitions": [],
                "quality": {
                    "status": "partial",
                    "unresolved": [{"id": "missing", "type": "missing_trigger_element"}],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updates = coverage_updates_from_artifacts(tmp_path, "project-1")

    assert updates["pages"] == [
        {
            "page_id": "page-partial",
            "path": "/partial",
            "artifact": "pages/page-partial.yaml",
            "status": "partial",
            "states": ["partial.root"],
        }
    ]
    assert updates["completed_actions"] == []
    assert updates["collection_groups"] == []
