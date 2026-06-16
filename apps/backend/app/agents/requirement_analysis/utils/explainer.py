"""
讲解生成器：把分析结果讲给测试人员

核心职责：
把业务洞察、领域模型、风险画像转换成易读的讲解文档
"""

from app.agents.requirement_analysis.core.models import (
    BusinessInsight,
    DomainModel,
    RiskProfile,
)


class ExplanationGenerator:
    """讲解生成器"""

    def generate(
        self,
        business_insight: BusinessInsight,
        domain_model: DomainModel,
        risk_profile: RiskProfile
    ) -> str:
        """
        生成讲解文档

        Args:
            business_insight: 业务洞察
            domain_model: 领域模型
            risk_profile: 风险画像

        Returns:
            str: Markdown格式的讲解文档
        """
        sections = []

        # 第1部分：业务理解
        sections.append(self._explain_business(business_insight))

        # 第2部分：领域模型
        sections.append(self._explain_domain(domain_model))

        # 第3部分：风险分析
        sections.append(self._explain_risks(risk_profile))

        # 第4部分：测试建议
        sections.append(self._generate_test_recommendations(risk_profile))

        return "\n\n---\n\n".join(sections)

    def _explain_business(self, insight: BusinessInsight) -> str:
        """生成业务理解部分"""
        parts = []

        parts.append("# 业务理解")
        parts.append("")
        parts.append(f"**业务领域**: {insight.domain}")
        parts.append("")
        parts.append(insight.summary)
        parts.append("")

        # 业务痛点
        if insight.pain_points:
            parts.append("## 业务痛点")
            parts.append("")
            for i, pain in enumerate(insight.pain_points, 1):
                parts.append(f"### {i}. {pain.description}")
                parts.append("")
                parts.append(f"**为什么是痛点**: {pain.reason}")
                parts.append("")
                parts.append(f"**影响**: {pain.impact}")
                parts.append("")

        # 核心价值
        if insight.core_values:
            parts.append("## 核心价值")
            parts.append("")
            for i, value in enumerate(insight.core_values, 1):
                priority_badge = "🔴" if value.priority == "high" else "🟡" if value.priority == "medium" else "🟢"
                parts.append(f"### {i}. {value.value} {priority_badge}")
                parts.append("")
                parts.append(f"**差异化**: {value.differentiation}")
                parts.append("")

        # 关键流程
        if insight.critical_flows:
            parts.append("## 关键流程")
            parts.append("")
            for i, flow in enumerate(insight.critical_flows, 1):
                parts.append(f"### {i}. {flow.name}")
                parts.append("")
                parts.append(f"**为什么关键**: {flow.why_critical}")
                parts.append("")
                parts.append(f"**流程描述**: {flow.description}")
                parts.append("")

                if flow.steps:
                    parts.append("**关键步骤**:")
                    parts.append("")
                    for step in flow.steps:
                        parts.append(f"- {step}")
                    parts.append("")

                if flow.decision_points:
                    parts.append("**决策点**:")
                    parts.append("")
                    for dp in flow.decision_points:
                        parts.append(f"- ⚠️ {dp}")
                    parts.append("")

        return "\n".join(parts)

    def _explain_domain(self, model: DomainModel) -> str:
        """生成领域模型部分"""
        parts = []

        parts.append("# 领域模型")
        parts.append("")
        parts.append(model.summary)
        parts.append("")

        # 核心概念
        if model.core_concepts:
            parts.append("## 核心概念")
            parts.append("")
            for concept in model.core_concepts:
                parts.append(f"### {concept.name}")
                parts.append("")
                parts.append(f"**本质**: {concept.essence}")
                parts.append("")
                if concept.examples:
                    parts.append("**示例**:")
                    parts.append("")
                    for example in concept.examples:
                        parts.append(f"- {example}")
                    parts.append("")

        # 领域实体
        if model.entities:
            parts.append("## 核心实体")
            parts.append("")
            for entity in model.entities:
                parts.append(f"### {entity.name}")
                parts.append("")
                parts.append(f"**存在意义**: {entity.why_exists}")
                parts.append("")
                parts.append(f"**生命周期**: {entity.lifecycle}")
                parts.append("")

                if entity.key_attributes:
                    parts.append("**关键属性**:")
                    parts.append("")
                    for attr in entity.key_attributes:
                        parts.append(f"- `{attr}`")
                    parts.append("")

                if entity.relationships:
                    parts.append("**关系**:")
                    parts.append("")
                    for rel in entity.relationships:
                        parts.append(f"- {rel}")
                    parts.append("")

        # 不变性约束
        if model.invariants:
            parts.append("## 不变性约束（测试必须验证）")
            parts.append("")
            for i, inv in enumerate(model.invariants, 1):
                parts.append(f"### {i}. {inv.constraint}")
                parts.append("")
                parts.append(f"**为什么重要**: {inv.why_important}")
                parts.append("")
                parts.append(f"**违反后果**: {inv.violation_consequence}")
                parts.append("")
                parts.append(f"**如何测试**: {inv.how_to_test}")
                parts.append("")

        # 状态机
        if model.state_machines:
            parts.append("## 状态机")
            parts.append("")
            for sm in model.state_machines:
                parts.append(f"### {sm.entity_name}")
                parts.append("")

                if sm.states:
                    parts.append(f"**状态**: {', '.join(sm.states)}")
                    parts.append("")

                if sm.critical_transitions:
                    parts.append("**⚠️ 容易出问题的转换**:")
                    parts.append("")
                    for trans in sm.critical_transitions:
                        parts.append(f"- {trans}")
                    parts.append("")

                if sm.mermaid_diagram:
                    parts.append("**状态图**:")
                    parts.append("")
                    parts.append("```mermaid")
                    parts.append(sm.mermaid_diagram)
                    parts.append("```")
                    parts.append("")

        return "\n".join(parts)

    def _explain_risks(self, profile: RiskProfile) -> str:
        """生成风险分析部分"""
        parts = []

        parts.append("# 风险分析")
        parts.append("")
        parts.append(profile.summary)
        parts.append("")

        # 复杂场景
        if profile.complex_scenarios:
            parts.append("## 复杂场景")
            parts.append("")
            for i, scenario in enumerate(profile.complex_scenarios, 1):
                impact_badge = "🔴" if scenario.impact == "high" else "🟡" if scenario.impact == "medium" else "🟢"
                parts.append(f"### {i}. {scenario.scenario} {impact_badge}")
                parts.append("")
                parts.append(f"**为什么复杂**: {scenario.why_complex}")
                parts.append("")
                parts.append(f"**复杂度来源**: {scenario.complexity_source}")
                parts.append("")

        # 风险根因
        if profile.root_causes:
            parts.append("## 风险根因分析")
            parts.append("")
            for i, risk in enumerate(profile.root_causes, 1):
                likelihood_badge = "🔴" if risk.likelihood == "high" else "🟡" if risk.likelihood == "medium" else "🟢"
                parts.append(f"### 风险{i}: {risk.risk_description} {likelihood_badge}")
                parts.append("")
                parts.append(f"**根本原因**: {risk.root_cause}")
                parts.append("")
                parts.append(f"**触发条件**: {risk.trigger_condition}")
                parts.append("")
                parts.append(f"**后果**: {risk.consequence}")
                parts.append("")

        # 边界条件
        if profile.boundary_conditions:
            parts.append("## 边界条件")
            parts.append("")
            for i, boundary in enumerate(profile.boundary_conditions, 1):
                parts.append(f"### {i}. {boundary.boundary}")
                parts.append("")
                parts.append(f"**边界行为**: {boundary.behavior_at_boundary}")
                parts.append("")
                parts.append(f"**超出边界**: {boundary.beyond_boundary}")
                parts.append("")

                if boundary.test_cases:
                    parts.append("**测试用例**:")
                    parts.append("")
                    for tc in boundary.test_cases:
                        parts.append(f"- {tc}")
                    parts.append("")

        return "\n".join(parts)

    def _generate_test_recommendations(self, profile: RiskProfile) -> str:
        """生成测试建议部分"""
        parts = []

        parts.append("# 测试策略建议")
        parts.append("")

        if not profile.test_strategies:
            parts.append("（待补充测试策略）")
            return "\n".join(parts)

        # 按优先级分组
        p0_strategies = [s for s in profile.test_strategies if s.priority == "P0"]
        p1_strategies = [s for s in profile.test_strategies if s.priority == "P1"]
        p2_strategies = [s for s in profile.test_strategies if s.priority == "P2"]

        if p0_strategies:
            parts.append("## P0 - 必须测试")
            parts.append("")
            for strategy in p0_strategies:
                parts.append(f"### {strategy.strategy}")
                parts.append("")

                if strategy.test_scenarios:
                    parts.append("**测试场景**:")
                    parts.append("")
                    for scenario in strategy.test_scenarios:
                        parts.append(f"- {scenario}")
                    parts.append("")

                if strategy.assertion_points:
                    parts.append("**断言点**:")
                    parts.append("")
                    for assertion in strategy.assertion_points:
                        parts.append(f"- ✓ {assertion}")
                    parts.append("")

        if p1_strategies:
            parts.append("## P1 - 重要测试")
            parts.append("")
            for strategy in p1_strategies:
                parts.append(f"### {strategy.strategy}")
                parts.append("")

                if strategy.test_scenarios:
                    parts.append("**测试场景**: " + ", ".join(strategy.test_scenarios))
                    parts.append("")

        if p2_strategies:
            parts.append("## P2 - 补充测试")
            parts.append("")
            for strategy in p2_strategies:
                parts.append(f"- {strategy.strategy}")

        return "\n".join(parts)


__all__ = ["ExplanationGenerator"]
