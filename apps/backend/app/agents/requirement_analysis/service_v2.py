"""
需求分析服务层 v2.0

提供需求分析的业务逻辑封装和配置管理
"""

import time
from datetime import datetime
from typing import Optional

from app.agents.requirement_analysis.agent_v2 import run_requirement_analysis_v2
from app.agents.requirement_analysis.schemas_v2 import (
    RequirementAnalysisInputV2,
    RequirementAnalysisResultV2,
    AuxiliaryDocument,
)


# 默认配置
DEFAULT_CONFIG = {
    "quality_thresholds": {
        "approved": 90,
        "conditional": 75,
    },
    "dimension_weights": {
        "completeness": 0.30,
        "clarity": 0.25,
        "testability": 0.25,
        "consistency": 0.20,
    },
    "nfr_categories": [
        "performance",
        "security",
        "availability",
        "scalability",
        "compatibility",
        "compliance",
    ],
    "auto_enhancement": {
        "enabled": True,
        "min_confidence": "medium",
    },
    "max_clarification_items": 100,
    "max_recommended_options": 2,
}


class RequirementAnalysisServiceV2:
    """需求分析服务 v2.0"""

    def __init__(self, model, config: Optional[dict] = None):
        """
        初始化服务

        Args:
            model: LLM 模型实例
            config: 自定义配置，会与默认配置合并
        """
        self.model = model
        self.config = {**DEFAULT_CONFIG, **(config or {})}

    async def analyze(
        self,
        input_data: RequirementAnalysisInputV2,
    ) -> RequirementAnalysisResultV2:
        """
        执行需求分析

        Args:
            input_data: 需求分析输入

        Returns:
            RequirementAnalysisResultV2: 分析结果
        """
        start_time = time.time()

        # 合并配置
        merged_config = {**self.config, **input_data.config}

        # 执行分析
        result = await run_requirement_analysis_v2(
            model=self.model,
            primary_markdown_content=input_data.primary_markdown_content,
            auxiliary_documents=input_data.auxiliary_documents,
            config=merged_config,
        )

        # 添加元数据
        execution_time_ms = int((time.time() - start_time) * 1000)
        result.metadata.update({
            "version": "2.0",
            "project_id": input_data.project_id,
            "document_id": input_data.document_id,
            "document_name": input_data.document_name,
            "run_id": input_data.run_id,
            "execution_time_ms": execution_time_ms,
            "execution_timestamp": datetime.now().isoformat(),
            "config": merged_config,
        })

        return result

    async def analyze_quick(
        self,
        primary_markdown_content: str,
        project_id: str = "quick",
        document_id: str = "quick",
        document_name: str = "快速分析",
    ) -> RequirementAnalysisResultV2:
        """
        快速分析（简化接口，无辅助文档）

        Args:
            primary_markdown_content: 主需求文档
            project_id: 项目ID
            document_id: 文档ID
            document_name: 文档名称

        Returns:
            RequirementAnalysisResultV2: 分析结果
        """
        input_data = RequirementAnalysisInputV2(
            project_id=project_id,
            document_id=document_id,
            document_name=document_name,
            run_id=f"quick-{int(time.time())}",
            primary_mapping_id="primary",
            primary_filename=document_name,
            primary_markdown_content=primary_markdown_content,
            auxiliary_documents=[],
            config={},
        )

        return await self.analyze(input_data)

    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config.copy()

    def update_config(self, config: dict):
        """更新配置"""
        self.config.update(config)


# 便捷函数

async def analyze_requirement_v2(
    model,
    primary_markdown_content: str,
    auxiliary_documents: Optional[list[AuxiliaryDocument]] = None,
    config: Optional[dict] = None,
    project_id: str = "default",
    document_id: str = "default",
    document_name: str = "需求文档",
) -> RequirementAnalysisResultV2:
    """
    便捷的需求分析函数

    Args:
        model: LLM 模型
        primary_markdown_content: 主需求文档
        auxiliary_documents: 辅助文档列表
        config: 配置
        project_id: 项目ID
        document_id: 文档ID
        document_name: 文档名称

    Returns:
        RequirementAnalysisResultV2: 分析结果
    """
    service = RequirementAnalysisServiceV2(model=model, config=config)

    input_data = RequirementAnalysisInputV2(
        project_id=project_id,
        document_id=document_id,
        document_name=document_name,
        run_id=f"run-{int(time.time())}",
        primary_mapping_id="primary",
        primary_filename=document_name,
        primary_markdown_content=primary_markdown_content,
        auxiliary_documents=auxiliary_documents or [],
        config={},
    )

    return await service.analyze(input_data)


__all__ = [
    "RequirementAnalysisServiceV2",
    "analyze_requirement_v2",
    "DEFAULT_CONFIG",
]
