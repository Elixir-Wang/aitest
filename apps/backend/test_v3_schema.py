"""
测试 v3.0 Schema 结构

验证新的测试驱动架构是否正确定义
"""

from app.agents.requirement_analysis.schemas import (
    ClarificationItem,
    ClarificationOption,
    ClarificationOutput,
    ClarificationSummary,
    TestCase,
    TestSurface,
)


def test_test_surface_structure():
    """测试 TestSurface 结构"""
    surface = TestSurface(
        surface_type="api",
        rationale="影响接口幂等性测试"
    )
    assert surface.surface_type == "api"
    assert surface.rationale == "影响接口幂等性测试"
    print("✅ TestSurface 结构正确")


def test_test_case_structure():
    """测试 TestCase 结构"""
    test_case = TestCase(
        test_id="TC-001",
        scenario="Given 用户已登录\nWhen 调用注册接口\nThen 应返回错误",
        test_type="negative",
        expected_result="返回 400 状态码",
        assertion_points=[
            "响应状态码为 400",
            "错误信息包含 'already logged in'",
            "不创建新用户"
        ],
        priority="P1"
    )
    assert test_case.test_id == "TC-001"
    assert test_case.test_type == "negative"
    assert len(test_case.assertion_points) == 3
    assert test_case.priority == "P1"
    print("✅ TestCase 结构正确")


def test_clarification_option_structure():
    """测试 ClarificationOption 结构"""
    option = ClarificationOption(
        option_id="OPT-001",
        label="按幂等处理",
        description="重复提交时返回已有结果，不产生重复数据",
        pros=["用户体验好", "符合最佳实践"],
        cons=["需要实现去重逻辑"],
        additional_tests=["验证5分钟内重复请求返回相同结果"],
        confidence="high",
        source="电商系统最佳实践",
        evidence_excerpt="API 文档中明确说明需要支持幂等性"
    )
    assert option.option_id == "OPT-001"
    assert len(option.pros) == 2
    assert len(option.cons) == 1
    assert option.confidence == "high"
    print("✅ ClarificationOption 结构正确")


def test_clarification_item_structure():
    """测试 ClarificationItem 结构"""
    item = ClarificationItem(
        item_id="CL-001",
        title="订单重复提交处理策略待确认",
        issue_category="concurrency_unclear",
        priority="P0",
        module_key="order_management",
        module_name="订单管理",
        source_stage="testability",

        decision_point="用户重复提交订单时系统的处理策略",
        why_clarify="当前需求未说明重复提交的处理规则，存在幂等性风险",
        test_impact="不澄清会导致：(1) 并发测试无法设计；(2) 无法验证是否产生重复订单；(3) 压测无法判定正确性",
        risk_scenario="Given 用户在订单确认页面\nWhen 用户连续点击两次'提交订单'\nThen 系统应按确认后的规则处理",

        affected_surfaces=[
            TestSurface(surface_type="api", rationale="影响接口幂等性"),
            TestSurface(surface_type="data_consistency", rationale="影响数据一致性")
        ],

        test_cases=[
            TestCase(
                test_id="TC-001",
                scenario="Given 用户已添加商品\nWhen 连续点击两次提交\nThen 只创建一个订单",
                test_type="concurrency",
                expected_result="第二次返回相同订单ID",
                assertion_points=["数据库只有一条记录", "两次返回相同ID", "余额仅扣减一次"],
                priority="P0"
            )
        ],

        options=[
            ClarificationOption(
                option_id="OPT-001",
                label="按幂等处理",
                description="基于请求唯一标识进行去重",
                pros=["用户体验好"],
                cons=["需要实现去重"],
                additional_tests=["验证重复请求"],
                confidence="high",
                source="最佳实践"
            )
        ],

        recommended_option_id="OPT-001",
        recommendation_rationale="符合行业最佳实践",
        resolution_status="has_options"
    )

    assert item.item_id == "CL-001"
    assert item.priority == "P0"
    assert item.issue_category == "concurrency_unclear"
    assert len(item.affected_surfaces) == 2
    assert len(item.test_cases) == 1
    assert len(item.options) == 1
    assert item.test_cases[0].test_type == "concurrency"
    print("✅ ClarificationItem 结构正确")


def test_clarification_output_structure():
    """测试 ClarificationOutput 结构"""
    output = ClarificationOutput(
        items=[
            ClarificationItem(
                item_id="CL-001",
                title="测试项",
                issue_category="rule_missing",
                priority="P1",
                module_key="test",
                module_name="测试",
                source_stage="completeness",
                decision_point="测试决策点",
                why_clarify="测试原因",
                test_impact="测试影响：(1) 影响1；(2) 影响2；(3) 影响3",
                risk_scenario="Given...When...Then...",
                affected_surfaces=[TestSurface(surface_type="api", rationale="测试")],
                test_cases=[
                    TestCase(
                        test_id="TC-001",
                        scenario="测试场景",
                        test_type="positive",
                        expected_result="测试结果",
                        assertion_points=["断言1", "断言2", "断言3"],
                        priority="P1"
                    )
                ],
                options=[],
                resolution_status="needs_input"
            )
        ],
        summary=ClarificationSummary(
            total=1,
            by_priority={"P0": 0, "P1": 1, "P2": 0, "P3": 0},
            by_category={"rule_missing": 1},
            by_resolution={"auto_resolved": 0, "has_options": 0, "needs_input": 1, "needs_research": 0},
            test_surfaces_coverage={"api": 1},
            total_test_cases=1,
            blocking_count=0,
            high_risk_count=1,
            recommended_actions=["优先处理 P1 项"]
        ),
        overall_assessment="需求存在 1 个高风险项，需要澄清",
        test_strategy_recommendations=["补充 API 契约测试"],
        generated_at="2024-01-15T10:00:00Z",
        model_version="test-driven"
    )

    assert len(output.items) == 1
    assert output.summary.total == 1
    assert output.summary.by_priority["P1"] == 1
    assert output.summary.high_risk_count == 1
    assert output.model_version == "test-driven"
    print("✅ ClarificationOutput 结构正确")


if __name__ == "__main__":
    print("🧪 开始测试 v3.0 Schema 结构...\n")

    try:
        test_test_surface_structure()
        test_test_case_structure()
        test_clarification_option_structure()
        test_clarification_item_structure()
        test_clarification_output_structure()

        print("\n🎉 所有测试通过！v3.0 Schema 结构正确")
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
