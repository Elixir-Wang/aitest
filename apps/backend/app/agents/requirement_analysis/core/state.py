"""
LangGraph 状态定义

定义需求分析工作流的状态结构
"""

from typing import TypedDict, Optional, List, Dict
from app.agents.requirement_analysis.core.schemas import (
    RequirementUnderstandingOutput,
    QualityAssessmentOutput,
    ClarificationOutput,
)


class RequirementAnalysisState(TypedDict):
    """需求分析工作流状态"""

    # ========== 输入 ==========
    primary_content: str  # 主需求文档
    auxiliary_docs: List[Dict]  # 辅助文档列表
    config: Dict  # 配置参数

    # ========== 项目信息 ==========
    project_id: str
    document_id: str
    document_name: str
    run_id: str

    # ========== 中间状态（各阶段输出）==========
    understanding: Optional[RequirementUnderstandingOutput]  # 需求理解结果
    quality: Optional[QualityAssessmentOutput]  # 质量评估结果
    clarification: Optional[ClarificationOutput]  # 待澄清内容

    # ========== 最终输出 ==========
    enhanced_requirement: Optional[str]  # 增强版需求文档
    analysis_report: Optional[str]  # 分析报告
    status: Optional[str]  # completed/needs_clarification/blocked

    # ========== 元数据 ==========
    metadata: Dict  # 执行信息（耗时、token消耗等）


__all__ = ["RequirementAnalysisState"]
