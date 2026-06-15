"""
QA视图生成器：统一测试信息输出

核心职责：
1. 生成测试清单（按优先级排序）
2. 汇总风险热点
3. 生成功能地图（Mermaid）
4. 汇总覆盖度分析
5. 集成所有可视化图表
"""

from typing import Optional
from app.agents.requirement_analysis.models import (
    TestScenarioInsight,
    DomainModel,
    TestabilityAssessment,
    QARequirementView,
    TestItem,
    CoverageAnalysis,
)


class QAViewGenerator:
    """QA视图生成器"""

    def generate(
        self,
        test_scenarios: TestScenarioInsight,
        domain_model: Optional[DomainModel],
        testability: TestabilityAssessment
    ) -> QARequirementView:
        """
        生成QA需求视图

        Args:
            test_scenarios: 测试场景洞察
            domain_model: 领域模型
            testability: 可测试性评估

        Returns:
            QARequirementView: QA需求视图
        """
        # 1. 生成测试清单（按优先级排序）
        test_checklist = self._generate_test_checklist(test_scenarios)

        # 2. 汇总风险热点
        risk_hotspots = test_scenarios.risk_hotspots

        # 3. 获取数据流图
        data_flow_diagram = test_scenarios.data_flow_mermaid

        # 4. 生成功能地图
        feature_map_diagram = self._generate_feature_map(test_scenarios)

        # 5. 收集状态机图
        state_machines = []
        if domain_model and domain_model.state_machines:
            state_machines = [sm.mermaid_diagram for sm in domain_model.state_machines]

        # 6. 生成覆盖度分析
        coverage_analysis = self._generate_coverage_analysis(
            test_scenarios, testability
        )

        # 7. 生成总结
        summary = self._generate_summary(
            test_scenarios, testability, coverage_analysis
        )

        return QARequirementView(
            test_checklist=test_checklist,
            risk_hotspots=risk_hotspots,
            data_flow_diagram=data_flow_diagram,
            feature_map_diagram=feature_map_diagram,
            state_machines=state_machines,
            coverage_analysis=coverage_analysis,
            testability_assessment=testability,
            summary=summary
        )

    def _generate_test_checklist(
        self, test_scenarios: TestScenarioInsight
    ) -> list[TestItem]:
        """生成测试清单，按优先级排序"""
        test_items = []

        for scenario in test_scenarios.test_scenarios:
            # 判断风险等级
            risk_level = "low"
            if scenario.priority == "P0":
                risk_level = "high"
            elif scenario.priority == "P1":
                risk_level = "medium"

            # 构造Given-When-Then描述
            gwt = f"**Given**: {scenario.given}\n**When**: {scenario.when}\n**Then**: {scenario.then}"

            test_item = TestItem(
                id=scenario.scenario_id,
                feature=scenario.title,
                scenario=scenario.title,
                priority=scenario.priority,
                test_type=scenario.test_type,
                given_when_then=gwt,
                assertion_points=scenario.assertion_points,
                test_data=scenario.test_data,
                risk_level=risk_level
            )
            test_items.append(test_item)

        # 按优先级排序（P0 > P1 > P2 > P3）
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        test_items.sort(key=lambda x: priority_order.get(x.priority, 99))

        return test_items

    def _generate_feature_map(
        self, test_scenarios: TestScenarioInsight
    ) -> Optional[str]:
        """生成功能地图（Mermaid mindmap）"""
        if not test_scenarios.features:
            return None

        # 按功能点分组
        feature_groups = {}
        for feature in test_scenarios.features:
            # 简单提取功能模块（从功能名称中提取）
            # 例如："用户登录" → "用户管理"
            parts = feature.feature_name.split("-")
            module = parts[0] if parts else "其他功能"

            if module not in feature_groups:
                feature_groups[module] = []
            feature_groups[module].append(feature.feature_name)

        # 生成mindmap
        lines = ["mindmap"]
        lines.append("  root((需求功能))")

        for module, features in feature_groups.items():
            lines.append(f"    {module}")
            for feature in features:
                # 简化功能名称，去掉模块前缀
                simple_name = feature.replace(f"{module}-", "").replace(module, "")
                if simple_name:
                    lines.append(f"      {simple_name}")

        return "\n".join(lines)

    def _generate_coverage_analysis(
        self,
        test_scenarios: TestScenarioInsight,
        testability: TestabilityAssessment
    ) -> CoverageAnalysis:
        """生成覆盖度分析"""
        total_features = len(test_scenarios.features)
        testable_features = len(testability.testable_features)
        untestable_features = len(testability.untestable_features)

        # 计算覆盖率
        coverage_percentage = 0.0
        if total_features > 0:
            coverage_percentage = (testable_features / total_features) * 100

        # 提取gaps
        gaps = [issue.description for issue in testability.untestable_features]

        return CoverageAnalysis(
            total_features=total_features,
            testable_features=testable_features,
            untestable_features=untestable_features,
            coverage_percentage=round(coverage_percentage, 2),
            gaps=gaps
        )

    def _generate_summary(
        self,
        test_scenarios: TestScenarioInsight,
        testability: TestabilityAssessment,
        coverage: CoverageAnalysis
    ) -> str:
        """生成QA视图总结"""
        lines = []

        # 基本统计
        lines.append(f"## 📊 测试概览")
        lines.append("")
        lines.append(f"- **总功能点**: {coverage.total_features}")
        lines.append(f"- **测试场景**: {len(test_scenarios.test_scenarios)}")
        lines.append(f"- **风险热点**: {len(test_scenarios.risk_hotspots)}")
        lines.append(f"- **可测试性评分**: {testability.score}/100")
        lines.append(f"- **测试覆盖率**: {coverage.coverage_percentage}%")
        lines.append("")

        # 优先级分布
        p0_count = sum(1 for s in test_scenarios.test_scenarios if s.priority == "P0")
        p1_count = sum(1 for s in test_scenarios.test_scenarios if s.priority == "P1")
        p2_count = sum(1 for s in test_scenarios.test_scenarios if s.priority == "P2")
        p3_count = sum(1 for s in test_scenarios.test_scenarios if s.priority == "P3")

        lines.append(f"## 🎯 测试优先级分布")
        lines.append("")
        lines.append(f"- **P0 (核心功能)**: {p0_count} 个")
        lines.append(f"- **P1 (重要功能)**: {p1_count} 个")
        lines.append(f"- **P2 (一般功能)**: {p2_count} 个")
        lines.append(f"- **P3 (补充测试)**: {p3_count} 个")
        lines.append("")

        # 测试类型分布
        functional_count = sum(1 for s in test_scenarios.test_scenarios if s.test_type == "functional")
        negative_count = sum(1 for s in test_scenarios.test_scenarios if s.test_type == "negative")
        boundary_count = sum(1 for s in test_scenarios.test_scenarios if s.test_type == "boundary")
        concurrency_count = sum(1 for s in test_scenarios.test_scenarios if s.test_type == "concurrency")

        lines.append(f"## 🔍 测试类型分布")
        lines.append("")
        lines.append(f"- **功能测试**: {functional_count} 个")
        lines.append(f"- **异常测试**: {negative_count} 个")
        lines.append(f"- **边界测试**: {boundary_count} 个")
        lines.append(f"- **并发测试**: {concurrency_count} 个")
        lines.append("")

        # 风险热点
        if test_scenarios.risk_hotspots:
            high_risk = [r for r in test_scenarios.risk_hotspots if r.priority == "P0"]
            if high_risk:
                lines.append(f"## ⚠️ 高风险区域 ({len(high_risk)}个)")
                lines.append("")
                for risk in high_risk[:3]:  # 只列前3个
                    lines.append(f"- **{risk.area}**: {risk.risk}")
                lines.append("")

        # 可测试性问题
        if testability.blocking_issues:
            lines.append(f"## 🚫 阻塞项 ({len(testability.blocking_issues)}个)")
            lines.append("")
            for issue in testability.blocking_issues[:5]:  # 只列前5个
                lines.append(f"- {issue}")
            lines.append("")

        # 建议
        lines.append(f"## 💡 测试建议")
        lines.append("")
        if testability.allow_knowledge_generation:
            lines.append("✅ **可测试性良好**，建议优先测试以下内容：")
            lines.append("")
            lines.append("1. 执行P0核心功能测试")
            lines.append("2. 关注高风险区域的并发和异常测试")
            lines.append("3. 补充边界值测试")
        else:
            lines.append("⚠️ **存在阻塞项**，建议先澄清以下问题再开始测试：")
            lines.append("")
            for i, issue in enumerate(testability.blocking_issues[:3], 1):
                lines.append(f"{i}. {issue}")

        return "\n".join(lines)


__all__ = ["QAViewGenerator"]
