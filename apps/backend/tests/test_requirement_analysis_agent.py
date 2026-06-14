def test_requirement_analysis_input_contract_only_contains_primary_fields():
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    assert set(RequirementAnalysisInput.model_fields) == {
        "project_id",
        "document_id",
        "document_name",
        "run_id",
        "primary_mapping_id",
        "primary_filename",
        "primary_markdown_content",
    }


def test_clarification_item_builds_generic_test_decision_fields():
    from app.agents.requirement_analysis.nodes.clarify_node import _create_clarification_item

    item = _create_clarification_item(
        {
            "id": "TC-1",
            "title": "测试覆盖待确认",
            "issue_type": "confirmation",
            "source": "testability",
            "module_key": "order_create",
            "module_name": "订单创建",
            "gap_type": "concurrency",
            "question": "请确认测试覆盖缺口：需求未说明重复提交或并发提交时是否允许创建多笔订单。",
            "impact": "无法编写订单数量、库存扣减次数和重复请求响应的断言。",
            "severity": "major",
            "current_text": "用户提交订单后生成订单记录并扣减库存。",
        },
        {"found": False, "confidence": "low", "answer": "", "source": ""},
    )

    assert item.clarification_bucket == "blocker"
    assert item.decision_point
    assert item.human_question == item.question
    assert "请确认“" in item.question
    assert "验收标准" not in item.question
    assert "data_consistency" in item.affected_surfaces
    assert "api" in item.affected_surfaces
    assert item.risk_scenario.startswith("Given ")
    assert item.draft_acceptance_tests
    assert len(item.decision_options) >= 2


def test_clarification_filter_rejects_generic_nfr_without_source():
    from app.agents.requirement_analysis.nodes.clarify_node import _is_useful_clarification_question

    assert not _is_useful_clarification_question(
        {
            "question": "缺少 compatibility 需求，需要定义什么指标？",
            "impact": "影响兼容性测试。",
            "source": "completeness",
            "issue_type": "missing",
            "current_text": "",
        }
    )
