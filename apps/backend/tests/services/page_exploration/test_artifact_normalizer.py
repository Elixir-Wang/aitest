from app.services.page_exploration.artifact_normalizer import normalize_snapshot_artifact


def _verified(code: str) -> dict:
    return {
        "code": code,
        "verification": {"checked": True, "unique": True, "visible": True},
    }


def test_normalize_snapshot_artifact_writes_compact_schema_4() -> None:
    artifact = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "百融百工",
            "state_context": {"state_id": "workspace.root", "state_type": "root"},
            "visible_text_blocks": ["整页不应持久化的文本"],
            "accessibility_tree": [{"role": "heading", "name": "百融百工"}],
            "elements": [
                {
                    "role": "button",
                    "name": "创建",
                    "action_type": "click",
                    "primary_selector": _verified("page.getByRole('button', { name: '创建' })"),
                }
            ],
        }
    )

    assert artifact["schema_version"] == "4.0"
    assert artifact["page"] == {
        "id": "page-workspace",
        "title": "百融百工",
        "normalized_path": "/workspace",
    }
    assert set(artifact) == {
        "schema_version",
        "page",
        "objects",
        "states",
        "elements",
        "quality",
    }
    assert artifact["elements"][0]["locator"] == {
        "strategy": "role",
        "role": "button",
        "name": "创建",
        "exact": True,
    }
    assert "assertion_texts" not in artifact
    assert "merge_history" not in artifact
    assert "context" not in artifact["elements"][0]


def test_normalize_snapshot_artifact_flattens_overlay_state_and_filters_background_elements() -> None:
    root = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "Workspace",
            "state_context": {"state_id": "workspace.root", "state_type": "root"},
            "elements": [
                {
                    "role": "button",
                    "name": "创建",
                    "action_type": "click",
                    "primary_selector": _verified("page.getByRole('button', { name: '创建' })"),
                }
            ],
        }
    )

    artifact = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "Workspace",
            "state_context": {
                "state_id": "workspace.create_agent_popover",
                "state_type": "popover",
                "parent_state_id": "workspace.root",
                "triggered_by": {
                    "from_state": "workspace.root",
                    "element_key": "button-创建",
                    "action": "click",
                    "url_changed": False,
                },
            },
            "overlay": {
                "id": "create-agent-popover",
                "role": "popover",
                "name": "创建智能体",
                "primary_selector": _verified("page.locator('.create-agent-dropdown')"),
            },
            "elements": [
                {
                    "role": "option",
                    "name": "自主规划 Agent",
                    "action_type": "click",
                    "overlay_id": "create-agent-popover",
                    "primary_selector": _verified("page.getByText('自主规划 Agent', { exact: true })"),
                },
                {
                    "role": "button",
                    "name": "背景按钮",
                    "action_type": "click",
                    "primary_selector": _verified("page.getByRole('button', { name: '背景按钮' })"),
                },
            ],
        },
        existing=root,
    )

    assert [state["id"] for state in artifact["states"]] == [
        "workspace.root",
        "workspace.create_agent_popover",
    ]
    assert artifact["states"][1]["parent"] == "workspace.root"
    assert [element["name"] for element in artifact["elements"]] == ["创建", "自主规划 Agent"]
    assert artifact["transitions"] == [
        {
            "id": "workspace.root--click--button-创建",
            "from_state": "workspace.root",
            "action": "click",
            "target": "button-创建",
            "to_state": "workspace.create_agent_popover",
            "url_changed": False,
        }
    ]


def test_normalize_snapshot_artifact_marks_missing_transition_target_unresolved() -> None:
    artifact = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "Workspace",
            "state_context": {
                "state_id": "workspace.popover",
                "state_type": "popover",
                "parent_state_id": "workspace.root",
                "triggered_by": {
                    "from_state": "workspace.root",
                    "element_key": "button-不存在",
                    "action": "click",
                },
            },
            "overlay": {"id": "popover", "role": "popover", "name": "菜单"},
            "elements": [],
        }
    )

    assert "transitions" not in artifact
    assert artifact["quality"] == {
        "status": "partial",
        "unresolved": [
            {
                "id": "workspace.popover:trigger",
                "type": "missing_trigger_element",
                "reason": "button-不存在",
            }
        ],
    }


def test_normalize_snapshot_artifact_groups_collection_representatives() -> None:
    artifact = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "Workspace",
            "state_context": {"state_id": "workspace.root", "state_type": "root"},
            "elements": [],
            "collections": [
                {
                    "key": "workspace.agent_cards",
                    "item_element": "workspace.agent_card",
                    "items": [
                        {
                            "name": "tmp",
                            "type": "自主规划 Agent",
                            "status": "已发布",
                            "actions": ["分析", "使用", "对话历史", "更多"],
                        },
                        {
                            "name": "无插件智能体2",
                            "type": "自主规划 Agent",
                            "status": "已发布",
                            "actions": ["分析", "使用", "对话历史", "更多"],
                        },
                    ],
                }
            ],
        }
    )

    assert artifact["collections"] == [
        {
            "key": "workspace.agent_cards",
            "item_element": "workspace.agent_card",
            "group_by": ["type", "status"],
            "groups": [
                {
                    "key": "自主规划 Agent:已发布",
                    "type": "自主规划 Agent",
                    "status": "已发布",
                    "representative": "tmp",
                    "actions": ["分析", "使用", "对话历史", "更多"],
                }
            ],
        }
    ]


def test_normalize_snapshot_artifact_uses_last_role_in_scoped_locator() -> None:
    artifact = normalize_snapshot_artifact(
        {
            "url": "https://example.test/workspace",
            "title": "Workspace",
            "state_context": {"state_id": "workspace.dialog", "state_type": "dialog"},
            "overlay": {"id": "dialog", "role": "dialog", "name": "创建智能体"},
            "elements": [
                {
                    "role": "button",
                    "name": "创建",
                    "action_type": "click",
                    "overlay_id": "dialog",
                    "primary_selector": _verified(
                        "page.getByRole('dialog', { name: '创建智能体' }).getByRole('button', { name: '创建' })"
                    ),
                }
            ],
        }
    )

    assert artifact["elements"][0]["locator"] == {
        "strategy": "role",
        "role": "button",
        "name": "创建",
        "exact": True,
    }
