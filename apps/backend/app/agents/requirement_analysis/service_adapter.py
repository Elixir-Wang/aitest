"""
需求分析服务入口 - 支持 v2/v3 版本切换

根据环境变量 REQUIREMENT_ANALYSIS_VERSION 决定使用哪个版本：
- v2: Codex CLI（当前默认）
- v3: LangChain + Agentic Search（新版本）
"""

from app.core import settings


async def analyze_requirement(analysis_input):
    """
    需求分析服务入口

    根据配置自动路由到 v2 或 v3

    Args:
        analysis_input: RequirementAnalysisInput (v2) 或 RequirementAnalysisInputV2 (v3)

    Returns:
        RequirementAnalysisOutput (v2) 或 RequirementAnalysisResultV2 (v3)
    """
    version = settings.REQUIREMENT_ANALYSIS_VERSION

    if version == "v3":
        # 使用 v3.0: LangChain + Agentic Search
        from app.agents.requirement_analysis.v3.workflow import run_requirement_analysis_v3
        from app.agents.requirement_analysis.schemas_v2 import (
            RequirementAnalysisInputV2,
            AuxiliaryDocument,
        )

        # 转换 v2 输入格式到 v3
        input_v3 = RequirementAnalysisInputV2(
            project_id=analysis_input.project_id,
            document_id=analysis_input.document_id,
            document_name=analysis_input.document_name,
            run_id=analysis_input.run_id,
            primary_mapping_id=analysis_input.primary_mapping_id,
            primary_filename=analysis_input.primary_filename,
            primary_markdown_content=analysis_input.primary_markdown_content,
            auxiliary_documents=[
                AuxiliaryDocument(
                    mapping_id=doc.mapping_id,
                    filename=doc.filename,
                    document_type="other",
                    markdown_content=doc.markdown_content,
                )
                for doc in analysis_input.auxiliary_documents
            ],
            config={},
        )

        # 执行 v3 分析
        result_v3 = await run_requirement_analysis_v3(input_v3)

        # 转换 v3 输出格式到 v2（保持接口兼容）
        from app.agents.requirement_analysis.primary_analysis.schemas import RequirementAnalysisOutput

        return RequirementAnalysisOutput(
            status=result_v3.status,
            analysis_summary=result_v3.quality_assessment.assessment_summary,
            preliminary_requirement_markdown=result_v3.enhanced_requirement_markdown or analysis_input.primary_markdown_content,
            analysis_report_markdown=result_v3.analysis_report_markdown,
            applied_supplements=[],  # v3 不需要这个字段
            maturity_assessment=result_v3.quality_assessment.scores,
            key_gaps=[gap.description for gap in result_v3.quality_assessment.completeness.functional_gaps[:5]],
            assumptions=[],
            modules=[],
            clarification_questions=[
                {
                    "id": item.item_id,
                    "question": item.question,
                    "priority": "HIGH" if item.severity == "blocker" else "MEDIUM",
                    "dimension": item.source,
                    "impact": item.impact,
                    "recommended_options": [
                        {
                            "id": opt.option_id,
                            "label": opt.label,
                            "answer_markdown": opt.answer_markdown,
                        }
                        for opt in item.recommended_options
                    ],
                }
                for item in result_v3.clarification.items
            ],
            conflicts=[],
            coverage_audit=[],
            quality_gate={
                "result": result_v3.quality_assessment.decision.result,
                "testability_score": result_v3.quality_assessment.scores.testability,
                "blocking_issues": result_v3.quality_assessment.decision.blocking_issues,
                "warnings": [],
            },
            next_actions=result_v3.quality_assessment.decision.recommended_actions,
        )

    else:
        # 使用 v2: Codex CLI（默认）
        from app.agents.requirement_analysis.primary_analysis.service import analyze_requirement as analyze_v2

        return await analyze_v2(analysis_input)


__all__ = ["analyze_requirement"]
