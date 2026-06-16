"""ClarificationItem v3 适配层测试。"""

from app.agents.requirement_analysis.core.schemas import (
    ClarificationItem,
    ClarificationOption,
    ClarificationOutput,
    ClarificationSummary,
    TestSurface,
)
from app.agents.requirement_analysis.utils.clarification_adapter import (
    clarification_item_to_api,
    is_pending_resolution_status,
)
from app.agents.requirement_analysis.utils.priority_sorter import sort_clarification_items
from app.agents.requirement_analysis.utils.report_generator import generate_clarification_report
from app.agents.requirement_analysis.utils.requirement_enhancer import (
    generate_enhanced_requirement,
    get_pending_items,
)


def _sample_item(**overrides) -> ClarificationItem:
    payload = {
        "item_id": "CL-001",
        "title": "订单重复提交策略待确认",
        "issue_category": "concurrency_unclear",
        "priority": "P0",
        "module_key": "order",
        "module_name": "订单模块",
        "source_stage": "testability",
        "decision_point": "用户重复提交订单时系统的处理策略",
        "why_clarify": "当前需求未说明重复提交的处理规则",
        "test_impact": "无法设计并发与幂等测试",
        "risk_scenario": "Given 待支付订单\nWhen 用户连续点击提交\nThen 系统行为未定义",
        "affected_surfaces": [TestSurface(surface_type="api", rationale="影响接口幂等性")],
        "options": [
            ClarificationOption(
                option_id="OPT-1",
                label="按幂等处理",
                description="重复提交返回同一订单号",
                source="测试最佳实践",
            )
        ],
        "resolution_status": "has_options",
    }
    payload.update(overrides)
    return ClarificationItem(**payload)


def test_clarification_item_to_api_maps_v3_fields() -> None:
    api_item = clarification_item_to_api(_sample_item())

    assert api_item["id"] == "CL-001"
    assert api_item["question"] == "用户重复提交订单时系统的处理策略"
    assert api_item["impact"] == "无法设计并发与幂等测试"
    assert api_item["severity"] == "blocker"
    assert api_item["priority"] == "P0"
    assert api_item["issue_category"] == "concurrency_unclear"
    assert api_item["options"][0]["answer_markdown"] == "重复提交返回同一订单号"


def test_generate_clarification_report_uses_v3_fields() -> None:
    clarification = ClarificationOutput(
        items=[_sample_item()],
        summary=ClarificationSummary(total=1),
        overall_assessment="存在 1 个 P0 阻塞项。",
        generated_at="2026-06-15T00:00:00Z",
    )

    report = generate_clarification_report(clarification)

    assert "P0 阻塞项" in report
    assert "用户重复提交订单时系统的处理策略" in report
    assert "无法设计并发与幂等测试" in report


def test_generate_enhanced_requirement_uses_auto_resolution() -> None:
    item = _sample_item(
        resolution_status="auto_resolved",
        auto_resolution="重复提交返回同一订单号",
        auto_resolution_source="接口规范.md / 3.2 幂等性",
    )

    enhanced = generate_enhanced_requirement("# 原始需求", [item])

    assert "订单重复提交策略待确认" in enhanced
    assert "重复提交返回同一订单号" in enhanced
    assert "接口规范.md / 3.2 幂等性" in enhanced


def test_sort_and_pending_items_use_v3_statuses() -> None:
    items = [
        _sample_item(item_id="CL-001", priority="P2", resolution_status="auto_resolved"),
        _sample_item(item_id="CL-002", priority="P0", resolution_status="needs_input"),
        _sample_item(item_id="CL-003", priority="P1", resolution_status="has_options"),
    ]

    sorted_items = sort_clarification_items(items)
    pending = get_pending_items(items)

    assert [item.item_id for item in sorted_items] == ["CL-002", "CL-003", "CL-001"]
    assert {item.item_id for item in pending} == {"CL-002", "CL-003"}
    assert is_pending_resolution_status("needs_research")
