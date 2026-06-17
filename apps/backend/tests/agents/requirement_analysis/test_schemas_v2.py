"""
需求分析 v2.0 单元测试
"""

import pytest
from app.agents.requirement_analysis.clarification.schemas import (
    ClarificationOutput,
    ClarificationItem,
    ClarificationOption,
    ClarificationSummary,
    TestSurface,
)
from app.agents.requirement_analysis.quality.schemas import (
    QualityAssessmentOutput,
    QualityIssueSummary,
    QualityDecision,
    CompletenessAssessment,
    ClarityAssessment,
    TestabilityAssessment,
    ConsistencyAssessment,
    NFRGap,
    FuzzyTerm,
)
from app.agents.requirement_analysis.understanding.schemas import (
    RequirementUnderstandingOutput,
    RequirementModule,
)
from app.agents.requirement_analysis.schemas import AuxiliaryDocument, RequirementAnalysisInputV2


def _clarification_item(**overrides) -> ClarificationItem:
    payload = {
        "item_id": "CLR-001",
        "title": "响应时间要求待确认",
        "issue_category": "boundary_undefined",
        "priority": "P1",
        "module_key": "order_management",
        "module_name": "订单管理",
        "source_stage": "completeness",
        "decision_point": "请确认响应时间要求？",
        "why_clarify": "当前需求未给出可度量指标。",
        "test_impact": "无法评估性能。",
        "risk_scenario": "Given 用户发起请求\nWhen 系统响应\nThen 响应时间应有明确阈值",
        "resolution_status": "needs_input",
    }
    payload.update(overrides)
    return ClarificationItem(**payload)


class TestSchemas:
    """测试数据模型"""

    def test_root_schemas_do_not_keep_unused_input_or_brief_fields(self):
        """根契约只保留实际消费的输入字段和下游摘要字段。"""
        assert "document_type" not in AuxiliaryDocument.model_fields
        assert "config" not in RequirementAnalysisInputV2.model_fields

        from app.agents.requirement_analysis import schemas

        assert hasattr(schemas, "QualityIssueBrief")
        assert hasattr(schemas, "QualityAssessmentBrief")

    def test_requirement_module(self):
        """测试需求模块创建"""
        module = RequirementModule(
            module_key="order_management",
            module_name="订单管理",
            summary="订单相关功能",
            capabilities=["创建订单", "支付订单"],
        )

        assert module.module_key == "order_management"
        assert module.module_name == "订单管理"
        assert len(module.capabilities) == 2

    def test_quality_issue_summary(self):
        """测试质量问题统计（替代评分）"""
        summary = QualityIssueSummary(
            completeness_issues=3,
            clarity_issues=5,
            testability_issues=4,
            consistency_issues=1,
            total_issues=13,
            by_severity={"blocker": 1, "major": 7, "minor": 5},
            has_blocker=True,
            can_proceed=False,
        )

        assert summary.completeness_issues == 3
        assert summary.total_issues == 13
        assert summary.has_blocker is True
        assert summary.can_proceed is False

    def test_nfr_gap(self):
        """测试 NFR 缺口"""
        gap = NFRGap(
            category="performance",
            description="未定义响应时间要求",
            impact="无法评估系统性能",
            severity="blocker",
            suggested_requirement="响应时间 < 2秒",
        )

        assert gap.category == "performance"
        assert gap.severity == "blocker"
        assert "2秒" in gap.suggested_requirement

    def test_fuzzy_term(self):
        """测试模糊词"""
        term = FuzzyTerm(
            term="快速",
            location="订单模块",
            current_text="系统应当快速响应",
            issue="无法度量",
            suggested_fix="响应时间 < 2秒",
        )

        assert term.term == "快速"
        assert "2秒" in term.suggested_fix

    def test_clarification_item(self):
        """测试待澄清项"""
        item = _clarification_item(
            priority="P0",
            resolution_status="needs_input",
        )

        assert item.priority == "P0"
        assert item.resolution_status == "needs_input"
        assert item.decision_point == "请确认响应时间要求？"
        assert item.affected_surfaces == []

    def test_clarification_item_supports_test_decision_fields(self):
        """测试待澄清项支持测试裁决字段，同时保持旧字段兼容"""
        item = _clarification_item(
            item_id="CLR-001",
            module_key="order_create",
            module_name="订单创建",
            title="重复提交规则待确认",
            source_stage="testability",
            priority="P0",
            issue_category="concurrency_unclear",
            decision_point="重复提交是否幂等",
            source_excerpt="用户提交订单后生成订单记录并扣减库存。",
            why_clarify="当前需求未说明重复提交是否创建多笔订单。",
            test_impact="无法断言订单数量、库存扣减次数和重复请求响应。",
            risk_scenario=(
                "Given 用户已提交一次有效订单请求\n"
                "When 相同请求再次提交\n"
                "Then 系统应按确认规则返回可观察结果"
            ),
            affected_surfaces=[
                TestSurface(surface_type="api"),
                TestSurface(surface_type="data_consistency"),
            ],
            options=[
                ClarificationOption(
                    option_id="decision-1",
                    label="按幂等处理",
                    description="重复请求返回首次创建结果。",
                    confidence="low",
                    source="测试视角推理",
                )
            ],
            recommendation_rationale="推荐优先确认幂等规则。该判断来自测试推理，需业务确认。",
            resolution_status="has_options",
        )

        assert item.decision_point == "重复提交是否幂等"
        assert item.source_excerpt == "用户提交订单后生成订单记录并扣减库存。"
        assert item.priority == "P0"
        assert [surface.surface_type for surface in item.affected_surfaces] == ["api", "data_consistency"]
        assert item.options[0].label == "按幂等处理"

    def test_clarification_summary(self):
        """测试澄清内容汇总"""
        summary = ClarificationSummary(
            total=10,
            by_priority={"P0": 1, "P1": 5, "P2": 4, "P3": 0},
            by_category={"boundary_undefined": 4, "contract_unclear": 3},
            by_resolution={"auto_resolved": 2, "has_options": 5, "needs_input": 3, "needs_research": 0},
        )

        assert summary.total == 10
        assert summary.by_resolution["needs_input"] == 3
        assert summary.by_priority["P0"] == 1


class TestPrioritySorter:
    """测试优先级排序"""

    def test_sort_clarification_items(self):
        """测试待澄清项排序"""
        from app.agents.requirement_analysis.utils.sorter import (
            sort_clarification_items,
        )

        items = [
            _clarification_item(
                item_id="1",
                priority="P3",
                resolution_status="needs_input",
            ),
            _clarification_item(
                item_id="2",
                priority="P0",
                resolution_status="needs_input",
            ),
            _clarification_item(
                item_id="3",
                priority="P1",
                resolution_status="auto_resolved",
            ),
        ]

        sorted_items = sort_clarification_items(items)

        # 验证排序：P0 + needs_input 应该在最前面
        assert sorted_items[0].item_id == "2"
        assert sorted_items[0].priority == "P0"
        assert sorted_items[0].resolution_status == "needs_input"


class TestReportGenerator:
    """测试报告生成"""

    def test_generate_analysis_report(self):
        """测试生成分析报告"""
        from app.agents.requirement_analysis.utils.report import (
            generate_analysis_report,
            generate_clarification_report,
            generate_quality_assurance_report,
        )

        # 准备测试数据
        understanding = RequirementUnderstandingOutput(
            modules=[
                RequirementModule(
                    module_key="test",
                    module_name="测试模块",
                    summary="测试",
                    capabilities=["功能1"],
                )
            ],
            risks=[],
            assumptions=[],
            understanding_summary="测试总结",
        )

        quality = QualityAssessmentOutput(
            summary=QualityIssueSummary(
                completeness_issues=3,
                clarity_issues=5,
                testability_issues=6,
                consistency_issues=1,
                total_issues=15,
                by_severity={"blocker": 1, "major": 8, "minor": 6},
                has_blocker=True,
                can_proceed=False,
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="存在15个问题需要澄清",
                blocking_issues=["缺少性能要求"],
                recommended_actions=["补充性能指标"],
            ),
            completeness=CompletenessAssessment(),
            clarity=ClarityAssessment(),
            testability=TestabilityAssessment(),
            consistency=ConsistencyAssessment(),
            assessment_summary="质量评估完成",
        )

        clarification = ClarificationOutput(
            items=[],
            summary=ClarificationSummary(
                total=5,
                by_resolution={"auto_resolved": 1, "has_options": 2, "needs_input": 2, "needs_research": 0},
            ),
            overall_assessment="共5个问题",
            generated_at="2026-06-17T00:00:00",
        )

        # 生成报告
        report = generate_analysis_report(understanding)
        quality_report = generate_quality_assurance_report(quality, clarification)
        clarification_report = generate_clarification_report(clarification)

        # 验证报告内容
        assert "# 需求分析报告" in report
        assert "测试模块" in report
        assert "```mermaid" in report
        assert "质量评分" not in report
        assert "质量分数" not in report
        assert "待澄清问题" not in report
        assert "## 3. 待澄清内容" not in report
        assert "73/100" not in report
        assert "# 质量保障报告" in quality_report
        assert "完整性" in quality_report
        assert "清晰度" in quality_report
        assert "可测试性" in quality_report
        assert "一致性" in quality_report
        assert "# 待澄清内容" in clarification_report

    def test_generate_clarification_report_groups_test_decision_items(self):
        """待澄清报告应按测试裁决分组展示"""
        from app.agents.requirement_analysis.utils.report import generate_clarification_report

        clarification = ClarificationOutput(
            items=[
                _clarification_item(
                    item_id="CLR-001",
                    module_key="order_create",
                    module_name="订单创建",
                    title="重复提交是否幂等待确认",
                    source_stage="testability",
                    priority="P0",
                    issue_category="concurrency_unclear",
                    decision_point="重复提交是否幂等",
                    source_excerpt="用户提交订单后生成订单记录并扣减库存。",
                    why_clarify="当前需求未说明重复提交是否创建多笔订单。",
                    test_impact="无法断言订单数量、库存扣减次数和重复请求响应。",
                    risk_scenario="Given 已提交一次有效请求\nWhen 相同请求再次提交\nThen 系统应按确认规则返回可观察结果",
                    affected_surfaces=[
                        TestSurface(surface_type="api"),
                        TestSurface(surface_type="data_consistency"),
                    ],
                    resolution_status="needs_input",
                )
            ],
            summary=ClarificationSummary(
                total=1,
                by_resolution={"auto_resolved": 0, "has_options": 0, "needs_input": 1, "needs_research": 0},
            ),
            overall_assessment="共1个问题",
            generated_at="2026-06-17T00:00:00",
        )

        report = generate_clarification_report(clarification)

        assert "### P0 阻塞项" in report
        assert "### P1 高风险" in report
        assert "### P2 中风险" in report
        assert "**澄清原因**" in report
        assert "**测试影响**" in report
        assert "**风险场景**" in report
        assert "**影响范围**" in report


class TestRequirementEnhancer:
    """测试需求增强器"""

    def test_generate_enhanced_requirement(self):
        """测试生成增强版需求"""
        from app.agents.requirement_analysis.utils.enhancer import (
            generate_enhanced_requirement,
        )

        original = "# 订单管理\n\n用户可以创建订单。"

        auto_resolved = [
            _clarification_item(
                item_id="CLR-001",
                module_key="order",
                module_name="订单管理",
                title="响应时间要求待确认",
                decision_point="响应时间要求是什么？",
                resolution_status="auto_resolved",
                auto_resolution="响应时间 < 2秒",
            )
        ]

        enhanced = generate_enhanced_requirement(original, auto_resolved)

        # 验证增强版文档包含必要内容
        assert "# 增强版需求文档" in enhanced
        assert "原始需求内容" in enhanced
        assert "自动补充的内容" in enhanced
        assert "订单管理" in enhanced
        assert "响应时间 < 2秒" in enhanced
        assert "[自动补充]" in enhanced

    def test_get_auto_resolved_items(self):
        """测试提取 auto_resolved 项"""
        from app.agents.requirement_analysis.utils.enhancer import (
            get_auto_resolved_items,
        )

        items = [
            _clarification_item(
                item_id="1",
                resolution_status="auto_resolved",
            ),
            _clarification_item(
                item_id="2",
                resolution_status="needs_input",
            ),
            _clarification_item(
                item_id="3",
                resolution_status="auto_resolved",
            ),
        ]

        auto_resolved = get_auto_resolved_items(items)

        assert len(auto_resolved) == 2
        assert all(item.resolution_status == "auto_resolved" for item in auto_resolved)

class TestQualityConversion:
    def test_convert_ambiguous_issue_without_interpretations_uses_fallbacks(self):
        from app.agents.requirement_analysis.quality.agent import convert_to_full_assessment
        from app.agents.requirement_analysis.quality.schemas import (
            QualityAssessmentSimple,
            QualityIssueFlat,
        )

        simple = QualityAssessmentSimple(
            issues=[
                QualityIssueFlat(
                    issue_id="CLAR-001",
                    dimension="clarity",
                    category="ambiguous",
                    severity="major",
                    title="歧义表述",
                    description="一句话多种理解",
                    location="登录模块",
                    current_text="用户登录后系统需要快速响应",
                    issue_reason="无法确定响应时间要求",
                    suggested_fix="登录后系统需在2秒内返回结果",
                    impact="无法设计性能测试",
                    extra={},
                )
            ],
            assessment_summary="识别出1个清晰度问题",
        )

        result = convert_to_full_assessment(simple)

        assert len(result.clarity.ambiguous_statements) == 1
        assert len(result.clarity.ambiguous_statements[0].possible_interpretations) >= 2


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
