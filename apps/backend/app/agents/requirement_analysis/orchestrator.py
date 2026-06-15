"""
深度理解编排器：编排整个分析流程

流程：
1. 业务分析（理解业务）
2. 领域建模（构建模型）
3. 风险识别（找出风险）
4. 生成讲解（输出文档）
"""

from datetime import datetime
from app.agents.requirement_analysis.models import DeepUnderstandingResult
from app.agents.requirement_analysis.analyzers.business import BusinessAnalyzer
from app.agents.requirement_analysis.analyzers.domain import DomainModeler
from app.agents.requirement_analysis.analyzers.risk import RiskIdentifier
from app.agents.requirement_analysis.explainer import ExplanationGenerator


class DeepUnderstandingOrchestrator:
    """深度理解编排器"""

    def __init__(self, model):
        """
        初始化编排器

        Args:
            model: LLM模型实例
        """
        self.model = model
        self.business_analyzer = BusinessAnalyzer(model)
        self.domain_modeler = DomainModeler(model)
        self.risk_identifier = RiskIdentifier(model)
        self.explainer = ExplanationGenerator()

    async def analyze(self, requirement_doc: str) -> DeepUnderstandingResult:
        """
        执行深度分析

        Args:
            requirement_doc: 需求文档内容

        Returns:
            DeepUnderstandingResult: 深度理解结果
        """
        # Step 1: 业务分析
        print("🔍 正在进行业务分析...")
        business_insight = await self.business_analyzer.analyze(requirement_doc)

        # Step 2: 领域建模
        print("🏗️ 正在构建领域模型...")
        domain_model = await self.domain_modeler.build_model(
            requirement_doc,
            business_insight
        )

        # Step 3: 风险识别
        print("⚠️ 正在识别测试风险...")
        risk_profile = await self.risk_identifier.identify(
            requirement_doc,
            business_insight,
            domain_model
        )

        # Step 4: 生成讲解
        print("📝 正在生成讲解文档...")
        explanation = self.explainer.generate(
            business_insight,
            domain_model,
            risk_profile
        )

        return DeepUnderstandingResult(
            business_insight=business_insight,
            domain_model=domain_model,
            risk_profile=risk_profile,
            explanation_markdown=explanation,
            generated_at=datetime.now().isoformat()
        )


__all__ = ["DeepUnderstandingOrchestrator"]
