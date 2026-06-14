"""
需求分析 v2.0 单元测试
"""

import pytest
from app.agents.requirement_analysis.schemas import (
    RequirementUnderstandingOutput,
    RequirementModule,
    QualityAssessmentOutput,
    QualityScores,
    QualityDecision,
    CompletenessAssessment,
    ClarityAssessment,
    TestabilityAssessment,
    ConsistencyAssessment,
    ClarificationOutput,
    ClarificationItem,
    ClarificationSummary,
    NFRGap,
    FuzzyTerm,
)


class TestSchemas:
    """测试数据模型"""

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

    def test_quality_scores(self):
        """测试质量分数"""
        scores = QualityScores(
            completeness=70,
            clarity=75,
            testability=60,
            consistency=95,
            overall=73,
        )

        assert scores.completeness == 70
        assert scores.overall == 73

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
        item = ClarificationItem(
            item_id="CLR-001",
            source="completeness",
            module_key="order_management",
            module_name="订单管理",
            question="请确认响应时间要求？",
            impact="无法评估性能",
            severity="blocker",
            current_text="系统应当快速",
            suggested_fix="响应时间 < 2秒",
            resolution_status="needs_manual",
        )

        assert item.severity == "blocker"
        assert item.resolution_status == "needs_manual"

    def test_clarification_summary(self):
        """测试澄清内容汇总"""
        summary = ClarificationSummary(
            total=10,
            auto_resolved=2,
            has_suggestions=5,
            needs_manual=3,
            by_severity={"blocker": 1, "major": 5, "minor": 4},
            by_source={"completeness": 4, "clarity": 3, "testability": 3},
        )

        assert summary.total == 10
        assert summary.needs_manual == 3
        assert summary.by_severity["blocker"] == 1


class TestPrioritySorter:
    """测试优先级排序"""

    def test_sort_clarification_items(self):
        """测试待澄清项排序"""
        from app.agents.requirement_analysis.utils.priority_sorter import (
            sort_clarification_items,
        )

        items = [
            ClarificationItem(
                item_id="1",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q1",
                impact="I1",
                severity="minor",
                resolution_status="needs_manual",
            ),
            ClarificationItem(
                item_id="2",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q2",
                impact="I2",
                severity="blocker",
                resolution_status="needs_manual",
            ),
            ClarificationItem(
                item_id="3",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q3",
                impact="I3",
                severity="major",
                resolution_status="auto_resolved",
            ),
        ]

        sorted_items = sort_clarification_items(items)

        # 验证排序：blocker + needs_manual 应该在最前面
        assert sorted_items[0].item_id == "2"
        assert sorted_items[0].severity == "blocker"
        assert sorted_items[0].resolution_status == "needs_manual"

    def test_group_by_severity(self):
        """测试按严重程度分组"""
        from app.agents.requirement_analysis.utils.priority_sorter import (
            group_by_severity,
        )

        items = [
            ClarificationItem(
                item_id="1",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q1",
                impact="I1",
                severity="blocker",
            ),
            ClarificationItem(
                item_id="2",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q2",
                impact="I2",
                severity="major",
            ),
            ClarificationItem(
                item_id="3",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q3",
                impact="I3",
                severity="blocker",
            ),
        ]

        groups = group_by_severity(items)

        assert len(groups["blocker"]) == 2
        assert len(groups["major"]) == 1
        assert len(groups["minor"]) == 0


class TestReportGenerator:
    """测试报告生成"""

    def test_generate_analysis_report(self):
        """测试生成分析报告"""
        from app.agents.requirement_analysis.utils.report_generator import (
            generate_analysis_report,
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
            scores=QualityScores(
                completeness=70,
                clarity=75,
                testability=60,
                consistency=95,
                overall=73,
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="总分73分",
                blocking_issues=["缺少性能要求"],
                recommended_actions=["补充性能指标"],
            ),
            completeness=CompletenessAssessment(score=70),
            clarity=ClarityAssessment(score=75),
            testability=TestabilityAssessment(score=60),
            consistency=ConsistencyAssessment(score=95),
            assessment_summary="质量评估完成",
        )

        clarification = ClarificationOutput(
            items=[],
            summary=ClarificationSummary(
                total=5,
                auto_resolved=1,
                has_suggestions=2,
                needs_manual=2,
            ),
            clarification_summary_text="共5个问题",
        )

        # 生成报告
        report = generate_analysis_report(understanding, quality, clarification)

        # 验证报告内容
        assert "# 需求分析报告" in report
        assert "质量评分" in report
        assert "73/100" in report
        assert "CONDITIONAL" in report  # 大写格式
        assert "测试模块" in report


class TestRequirementEnhancer:
    """测试需求增强器"""

    def test_generate_enhanced_requirement(self):
        """测试生成增强版需求"""
        from app.agents.requirement_analysis.utils.requirement_enhancer import (
            generate_enhanced_requirement,
        )

        original = "# 订单管理\n\n用户可以创建订单。"

        auto_resolved = [
            ClarificationItem(
                item_id="CLR-001",
                source="completeness",
                module_key="order",
                module_name="订单管理",
                question="响应时间要求是什么？",
                impact="无法评估性能",
                severity="major",
                current_text="系统应当快速",
                suggested_fix="响应时间 < 2秒",
                resolution_status="auto_resolved",
                evidence=[],
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
        from app.agents.requirement_analysis.utils.requirement_enhancer import (
            get_auto_resolved_items,
        )

        items = [
            ClarificationItem(
                item_id="1",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q1",
                impact="I1",
                severity="major",
                resolution_status="auto_resolved",
            ),
            ClarificationItem(
                item_id="2",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q2",
                impact="I2",
                severity="major",
                resolution_status="needs_manual",
            ),
            ClarificationItem(
                item_id="3",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q3",
                impact="I3",
                severity="minor",
                resolution_status="auto_resolved",
            ),
        ]

        auto_resolved = get_auto_resolved_items(items)

        assert len(auto_resolved) == 2
        assert all(item.resolution_status == "auto_resolved" for item in auto_resolved)

    def test_get_pending_items(self):
        """测试提取待处理项"""
        from app.agents.requirement_analysis.utils.requirement_enhancer import (
            get_pending_items,
        )

        items = [
            ClarificationItem(
                item_id="1",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q1",
                impact="I1",
                severity="major",
                resolution_status="auto_resolved",
            ),
            ClarificationItem(
                item_id="2",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q2",
                impact="I2",
                severity="major",
                resolution_status="needs_manual",
            ),
            ClarificationItem(
                item_id="3",
                source="completeness",
                module_key="test",
                module_name="测试",
                question="Q3",
                impact="I3",
                severity="minor",
                resolution_status="has_suggestions",
            ),
        ]

        pending = get_pending_items(items)

        assert len(pending) == 2
        assert all(
            item.resolution_status in ["needs_manual", "has_suggestions"]
            for item in pending
        )


class TestService:
    """测试服务层"""

    def test_default_config(self):
        """测试默认配置"""
        from app.agents.requirement_analysis.service import DEFAULT_CONFIG

        assert "quality_thresholds" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["quality_thresholds"]["approved"] == 90
        assert DEFAULT_CONFIG["dimension_weights"]["completeness"] == 0.30

    def test_service_initialization(self):
        """测试服务初始化"""
        from app.agents.requirement_analysis.service import (
            RequirementAnalysisService,
        )

        service = RequirementAnalysisService(model=None)
        config = service.get_config()

        assert "quality_thresholds" in config
        assert config["quality_thresholds"]["approved"] == 90


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
