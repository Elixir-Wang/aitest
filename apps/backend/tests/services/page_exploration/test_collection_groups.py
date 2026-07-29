from app.services.page_exploration.collection_groups import group_collection_items


def test_group_collection_items_uses_one_representative_for_duplicate_type_status_and_actions() -> None:
    groups = group_collection_items(
        [
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
                "actions": ["更多", "对话历史", "使用", "分析"],
            },
        ]
    )

    assert groups == [
        {
            "key": "自主规划 Agent:已发布",
            "type": "自主规划 Agent",
            "status": "已发布",
            "representative": "tmp",
            "actions": ["分析", "使用", "对话历史", "更多"],
        }
    ]


def test_group_collection_items_separates_type_and_status() -> None:
    groups = group_collection_items(
        [
            {
                "name": "test",
                "type": "Multi-Agent",
                "status": "草稿",
                "actions": ["编辑", "更多"],
            },
            {
                "name": "published",
                "type": "Multi-Agent",
                "status": "已发布",
                "actions": ["使用", "对话历史", "更多"],
            },
            {
                "name": "workflow",
                "type": "任务流 Agent",
                "status": "已发布",
                "actions": ["分析", "使用", "调用历史", "更多"],
            },
        ]
    )

    assert [group["key"] for group in groups] == [
        "Multi-Agent:草稿",
        "Multi-Agent:已发布",
        "任务流 Agent:已发布",
    ]


def test_group_collection_items_adds_simple_suffix_when_actions_differ() -> None:
    groups = group_collection_items(
        [
            {
                "name": "first",
                "type": "自主规划 Agent",
                "status": "已发布",
                "actions": ["分析", "使用", "更多"],
            },
            {
                "name": "second",
                "type": "自主规划 Agent",
                "status": "已发布",
                "actions": ["编辑", "删除", "更多"],
            },
        ]
    )

    assert [group["key"] for group in groups] == [
        "自主规划 Agent:已发布",
        "自主规划 Agent:已发布:2",
    ]
    assert groups[1]["representative"] == "second"


def test_group_collection_items_ignores_items_without_type_or_status() -> None:
    groups = group_collection_items(
        [
            {"name": "unknown", "type": "", "status": "已发布", "actions": ["使用"]},
            {"name": "known", "type": "写作 Agent", "status": "已发布", "actions": ["使用"]},
        ]
    )

    assert [group["representative"] for group in groups] == ["known"]

