"""
QA导向需求分析编排器

核心理念：
- 测试场景优先，而非业务分析优先
- 输出可执行的测试信息
- Token优化，只传递摘要
- 统一的QA视图
"""

from datetime import datetime
from typing import Optional
from app.agents.requirement_analysis.models import (
    QARequirementView,
    TestScenarioInsight,
    DomainModel,
    TestabilityAssessment,
)
from app.agents.requirement_analysis.analyzers.test_scenario import TestScenarioExtractor
from app.agents.requirement_analysis.analyzers.domain import DomainModeler
from app.agents.requirement_analysis.analyzers.testability import TestabilityAssessor
from app.agents.requirement_analysis.qa_view_generator import QAViewGenerator


class QAOrientedRequirementOrchestrator:
    """QA导向的需求分析编排器"""

    def __init__(self, model):
        """
        初始化编排器

        Args:
            model: LLM模型实例
        """
        self.model = model
        self.test_scenario_extractor = TestScenarioExtractor(model)
        self.domain_modeler = DomainModeler(model)
        self.testability_assessor = TestabilityAssessor(model)
        self.qa_view_generator = QAViewGenerator()

    async def analyze(
        self,
        requirement_doc: str,
        include_domain_model: bool = True
    ) -> QARequirementView:
        """
        执行QA导向的需求分析

        Args:
            requirement_doc: 需求文档内容
            include_domain_model: 是否包含领域建模（用于状态机生成）

        Returns:
            QARequirementView: QA需求视图
        """
        # Step 1: 测试场景提取（核心，最重要）
        print("🎯 正在提取测试场景...")
        test_scenarios = await self.test_scenario_extractor.extract(requirement_doc)
        print(f"   ✓ 提取了 {len(test_scenarios.features)} 个功能点")
        print(f"   ✓ 生成了 {len(test_scenarios.test_scenarios)} 个测试场景")
        print(f"   ✓ 识别了 {len(test_scenarios.risk_hotspots)} 个风险热点")

        # Step 2: 领域建模（可选，主要用于状态机）
        domain_model = None
        if include_domain_model:
            print("\n🏗️ 正在构建领域模型...")
            try:
                # Token优化：只传递摘要，不传完整文档
                domain_model = await self.domain_modeler.build_model(
                    requirement_doc=self._truncate_doc(requirement_doc, max_chars=5000),
                    business_insight=self._create_business_summary(test_scenarios)
                )
                print(f"   ✓ 识别了 {len(domain_model.entities)} 个核心实体")
                print(f"   ✓ 生成了 {len(domain_model.state_machines)} 个状态机")
            except Exception as e:
                print(f"   ⚠️ 领域建模失败（非阻塞）: {str(e)}")
                domain_model = None

        # Step 3: 可测试性评估
        print("\n✅ 正在评估可测试性...")
        testability = await self.testability_assessor.assess(
            test_scenarios=test_scenarios,
            domain_model=domain_model
        )
        print(f"   ✓ 可测试性评分: {testability.score}/100")
        print(f"   ✓ 可测试功能: {len(testability.testable_features)} 个")
        print(f"   ✓ 不可测试功能: {len(testability.untestable_features)} 个")
        if testability.blocking_issues:
            print(f"   ⚠️ 发现 {len(testability.blocking_issues)} 个阻塞项")

        # Step 4: 生成QA视图
        print("\n📋 正在生成QA视图...")
        qa_view = self.qa_view_generator.generate(
            test_scenarios=test_scenarios,
            domain_model=domain_model,
            testability=testability
        )
        print(f"   ✓ 测试清单: {len(qa_view.test_checklist)} 项")
        print(f"   ✓ 测试覆盖率: {qa_view.coverage_analysis.coverage_percentage}%")
        print(f"   ✓ 是否允许知识库生成: {'是' if testability.allow_knowledge_generation else '否'}")

        print("\n✨ 需求分析完成！")
        return qa_view

    def _truncate_doc(self, doc: str, max_chars: int = 5000) -> str:
        """
        截断文档，减少Token使用

        Args:
            doc: 原始文档
            max_chars: 最大字符数

        Returns:
            截断后的文档
        """
        if len(doc) <= max_chars:
            return doc

        # 保留前面的内容（通常包含核心需求）
        truncated = doc[:max_chars]

        # 在最后一个句号或换行处截断，避免截断句子
        last_period = truncated.rfind("。")
        last_newline = truncated.rfind("\n")
        cut_point = max(last_period, last_newline)

        if cut_point > max_chars // 2:  # 至少保留一半
            truncated = truncated[:cut_point + 1]

        return truncated + "\n\n...(文档已截断，保留核心部分)"

    def _create_business_summary(self, test_scenarios: TestScenarioInsight) -> str:
        """
        从测试场景创建业务摘要（替代完整的BusinessInsight）

        Args:
            test_scenarios: 测试场景洞察

        Returns:
            业务摘要字符串
        """
        lines = []

        # 摘要
        lines.append(f"## 业务摘要\n{test_scenarios.summary}")
        lines.append("")

        # 关键功能
        lines.append("## 关键功能")
        for i, feature in enumerate(test_scenarios.features[:5], 1):  # 只取前5个
            lines.append(f"{i}. {feature.feature_name}")
        lines.append("")

        # 风险热点
        if test_scenarios.risk_hotspots:
            lines.append("## 风险热点")
            for risk in test_scenarios.risk_hotspots[:3]:  # 只取前3个
                lines.append(f"- {risk.area}: {risk.risk}")

        return "\n".join(lines)

    async def analyze_simple(self, requirement_doc: str) -> TestScenarioInsight:
        """
        简化版分析：只提取测试场景，不做领域建模和可测试性评估

        适用场景：快速预览、Token预算有限

        Args:
            requirement_doc: 需求文档内容

        Returns:
            TestScenarioInsight: 测试场景洞察
        """
        print("🎯 正在提取测试场景（简化模式）...")
        test_scenarios = await self.test_scenario_extractor.extract(requirement_doc)
        print(f"   ✓ 提取了 {len(test_scenarios.features)} 个功能点")
        print(f"   ✓ 生成了 {len(test_scenarios.test_scenarios)} 个测试场景")
        print("\n✨ 需求分析完成（简化模式）！")
        return test_scenarios


__all__ = ["QAOrientedRequirementOrchestrator"]
