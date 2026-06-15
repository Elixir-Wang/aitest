"""
综合QA编排器

整合快速理解、测试场景提取、可测试性评估，生成完整的QA视图
"""

from app.agents.requirement_analysis.requirement_understanding_assistant import (
    RequirementUnderstandingAssistant,
)
from app.agents.requirement_analysis.analyzers.test_scenario import TestScenarioExtractor
from app.agents.requirement_analysis.analyzers.testability import TestabilityAssessor
from app.agents.requirement_analysis.models import (
    ComprehensiveQAView,
    TestItem,
    CoverageAnalysis,
    AllDiagrams,
)


class ComprehensiveQAOrchestrator:
    """综合QA编排器（整合快速理解 + 测试场景 + 可测试性）"""

    def __init__(self, model):
        """
        初始化

        Args:
            model: LLM模型实例
        """
        self.understanding_assistant = RequirementUnderstandingAssistant(model)
        self.scenario_extractor = TestScenarioExtractor(model)
        self.testability_assessor = TestabilityAssessor(model)
        self.model = model

    async def analyze(self, requirement_doc: str) -> ComprehensiveQAView:
        """
        完整分析流程

        Args:
            requirement_doc: 需求文档内容

        Returns:
            ComprehensiveQAView: 综合QA视图
        """
        print("=" * 80)
        print("🚀 开始需求分析（综合模式）")
        print("=" * 80)

        # ========== Step 1: 快速理解（3-5分钟） ==========
        print("\n📖 第1步：生成快速理解视图...")
        quick_view = await self.understanding_assistant.generate_quick_view(requirement_doc)
        print(f"   ✓ 智能摘要生成完成")
        print(f"   ✓ 功能地图生成完成")
        print(f"   ✓ 核心流程图生成完成")
        print(f"   ✓ 快速FAQ生成完成（{len(quick_view.faq)}个问题）")

        # ========== Step 2: 测试场景提取（10-15分钟） ==========
        print("\n🎯 第2步：提取测试场景...")
        test_scenarios = await self.scenario_extractor.extract(requirement_doc)
        print(f"   ✓ 提取了 {len(test_scenarios.features)} 个功能点")
        print(f"   ✓ 生成了 {len(test_scenarios.test_scenarios)} 个测试场景")
        print(f"   ✓ 识别了 {len(test_scenarios.risk_hotspots)} 个风险热点")

        # ========== Step 3: 可测试性评估 ==========
        print("\n✅ 第3步：评估可测试性...")
        testability = await self.testability_assessor.assess(test_scenarios)
        print(f"   ✓ 可测试性评分: {testability.score}/100")
        print(f"   ✓ 可测试功能: {len(testability.testable_features)}个")
        print(f"   ✓ 阻塞项: {len(testability.blocking_issues)}个")

        # ========== Step 4: 生成综合QA视图 ==========
        print("\n📋 第4步：生成综合QA视图...")

        # 生成测试清单
        test_checklist = self._generate_test_checklist(test_scenarios, testability)
        print(f"   ✓ 测试清单生成完成（{len(test_checklist)}项）")

        # 生成覆盖度分析
        coverage = self._generate_coverage_analysis(test_scenarios, testability)
        print(f"   ✓ 覆盖度分析完成（{coverage.coverage_percentage:.1f}%）")

        # 整合所有图表
        all_diagrams = AllDiagrams(
            feature_map=quick_view.feature_map_diagram,
            core_flow=quick_view.core_flow_diagram,
            data_flow=test_scenarios.data_flow_mermaid,
            state_machines=[],  # 如果有状态机则添加
        )
        print(f"   ✓ 可视化图表整合完成")

        # 生成综合总结
        summary = self._generate_summary(quick_view, test_scenarios, testability, coverage)

        print("\n" + "=" * 80)
        print("✨ 需求分析完成")
        print("=" * 80)

        return ComprehensiveQAView(
            quick_understanding=quick_view,
            test_scenarios=test_scenarios,
            testability=testability,
            test_checklist=test_checklist,
            coverage_analysis=coverage,
            all_diagrams=all_diagrams,
            summary=summary,
        )

    def _generate_test_checklist(self, test_scenarios, testability) -> list[TestItem]:
        """生成测试清单（按优先级排序）"""
        test_items = []

        for scenario in test_scenarios.test_scenarios:
            # 判断风险等级
            risk_level = "medium"
            for hotspot in test_scenarios.risk_hotspots:
                if hotspot.priority in ["P0", "P1"]:
                    risk_level = "high"
                    break

            test_item = TestItem(
                id=scenario.scenario_id,
                feature=scenario.title,
                scenario=f"{scenario.given} -> {scenario.when} -> {scenario.then}",
                priority=scenario.priority,
                test_type=scenario.test_type,
                given_when_then=f"Given: {scenario.given}\nWhen: {scenario.when}\nThen: {scenario.then}",
                assertion_points=scenario.assertion_points,
                test_data=scenario.test_data,
                risk_level=risk_level,
            )
            test_items.append(test_item)

        # 按优先级排序（P0 > P1 > P2 > P3）
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        test_items.sort(key=lambda x: priority_order.get(x.priority, 99))

        return test_items

    def _generate_coverage_analysis(self, test_scenarios, testability) -> CoverageAnalysis:
        """生成覆盖度分析"""
        total_features = len(test_scenarios.features)
        testable_features = len(testability.testable_features)
        untestable_features = len(testability.untestable_features)

        coverage_percentage = (
            (testable_features / total_features * 100) if total_features > 0 else 0
        )

        # 收集需求不清的地方
        gaps = []
        for issue in testability.untestable_features:
            if issue.issue_type == "vague_description":
                gaps.append(f"{issue.feature_name}: {issue.description}")

        return CoverageAnalysis(
            total_features=total_features,
            testable_features=testable_features,
            untestable_features=untestable_features,
            coverage_percentage=coverage_percentage,
            gaps=gaps,
        )

    def _generate_summary(self, quick_view, test_scenarios, testability, coverage) -> str:
        """生成综合总结"""
        summary_parts = []

        # 快速理解部分
        summary_parts.append(f"## 需求概述\n{quick_view.summary.core_function}")
        summary_parts.append(
            f"\n复杂度: {quick_view.summary.estimated_complexity.upper()}"
        )

        # 测试场景部分
        summary_parts.append(
            f"\n## 测试场景\n- 功能点: {len(test_scenarios.features)}个"
        )
        summary_parts.append(f"- 测试场景: {len(test_scenarios.test_scenarios)}个")
        summary_parts.append(f"- 风险热点: {len(test_scenarios.risk_hotspots)}个")

        # 可测试性部分
        summary_parts.append(f"\n## 可测试性\n- 评分: {testability.score}/100")
        summary_parts.append(f"- 阻塞项: {len(testability.blocking_issues)}个")

        # 覆盖度部分
        summary_parts.append(
            f"\n## 测试覆盖度\n- 覆盖率: {coverage.coverage_percentage:.1f}%"
        )
        summary_parts.append(
            f"- 可测试: {coverage.testable_features}/{coverage.total_features}个功能点"
        )

        # 关键风险
        if quick_view.summary.key_risks:
            summary_parts.append(
                f"\n## 关键风险\n" + "\n".join(f"- {risk}" for risk in quick_view.summary.key_risks)
            )

        return "\n".join(summary_parts)

    async def analyze_simple(self, requirement_doc: str, max_doc_length: int = 5000):
        """
        简化分析（适用于长文档，进行token优化）

        Args:
            requirement_doc: 需求文档内容
            max_doc_length: 最大文档长度（字符数）

        Returns:
            ComprehensiveQAView: 综合QA视图
        """
        # 截断文档（保留关键信息）
        truncated_doc = self._truncate_doc(requirement_doc, max_doc_length)

        return await self.analyze(truncated_doc)

    def _truncate_doc(self, doc: str, max_length: int) -> str:
        """
        智能截断文档

        Args:
            doc: 原始文档
            max_length: 最大长度

        Returns:
            str: 截断后的文档
        """
        if len(doc) <= max_length:
            return doc

        # 优先保留开头和关键部分
        return doc[:max_length] + "\n\n... (文档已截断)"
