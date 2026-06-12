"""
需求分析 API 路由 v2.0

提供 FastAPI 路由定义
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.agents.requirement_analysis.schemas_v2 import (
    RequirementAnalysisInputV2,
    RequirementAnalysisResultV2,
)
from app.agents.requirement_analysis.service_v2 import (
    RequirementAnalysisServiceV2,
    DEFAULT_CONFIG,
)


router = APIRouter(
    prefix="/api/requirement-analysis/v2",
    tags=["Requirement Analysis v2"],
)


# 响应模型
class AnalyzeResponse(BaseModel):
    """分析响应"""
    success: bool = True
    data: RequirementAnalysisResultV2
    message: str = "分析完成"


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: dict = Field(
        description="错误信息",
        examples=[{
            "code": "VALIDATION_ERROR",
            "message": "primary_markdown_content 不能为空",
            "details": {}
        }]
    )


class ConfigResponse(BaseModel):
    """配置响应"""
    config: dict


# 依赖注入：获取服务实例
def get_analysis_service():
    """
    获取需求分析服务实例

    TODO: 实际项目中应该从依赖注入容器获取，并注入真实的 LLM 模型
    """
    # 这里需要注入实际的 LLM 模型
    # from app.core.llm import get_llm_model
    # model = get_llm_model()

    # 临时：返回 None，调用方需要自行处理
    return RequirementAnalysisServiceV2(model=None, config=DEFAULT_CONFIG)


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="执行需求分析",
    description="执行完整的需求分析流程，包括需求理解、质量评估、待澄清内容识别",
)
async def analyze_requirement(
    input_data: RequirementAnalysisInputV2,
    service: RequirementAnalysisServiceV2 = Depends(get_analysis_service),
):
    """
    执行需求分析

    ## 请求参数

    - **project_id**: 项目ID
    - **document_id**: 文档ID
    - **document_name**: 文档名称
    - **primary_markdown_content**: 主需求文档（Markdown 格式）
    - **auxiliary_documents**: 辅助文档列表（可选）
    - **config**: 自定义配置（可选）

    ## 响应

    返回完整的分析结果，包括：
    - 需求理解结果
    - 质量评估结果（含 NFR 评估）
    - 待澄清内容（按优先级排序）
    - 分析报告（Markdown 格式）

    ## 状态码

    - **200**: 成功
    - **400**: 请求参数错误
    - **500**: 服务器内部错误
    """
    try:
        # 验证输入
        if not input_data.primary_markdown_content.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "primary_markdown_content 不能为空",
                    "details": {}
                }
            )

        # 执行分析
        result = await service.analyze(input_data)

        return AnalyzeResponse(
            success=True,
            data=result,
            message="分析完成"
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e),
                "details": {}
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "分析过程中发生错误",
                "details": {"error": str(e)}
            }
        )


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="获取默认配置",
    description="获取需求分析的默认配置参数",
)
async def get_config():
    """
    获取默认配置

    返回系统默认的配置参数，包括：
    - 质量阈值
    - 维度权重
    - NFR 类别
    - 自动增强配置
    """
    return ConfigResponse(config=DEFAULT_CONFIG)


@router.get(
    "/health",
    summary="健康检查",
    description="检查服务健康状态",
)
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "requirement-analysis-v2",
        "version": "2.0.0"
    }


# 快速分析接口（简化版）
class QuickAnalyzeRequest(BaseModel):
    """快速分析请求"""
    primary_markdown_content: str = Field(
        description="主需求文档（Markdown 格式）",
        min_length=10,
        max_length=100000,
    )
    project_id: str = Field(default="quick", description="项目ID")
    document_name: str = Field(default="快速分析", description="文档名称")


@router.post(
    "/quick-analyze",
    response_model=AnalyzeResponse,
    summary="快速分析（无辅助文档）",
    description="简化版的需求分析接口，不需要提供辅助文档",
)
async def quick_analyze(
    request: QuickAnalyzeRequest,
    service: RequirementAnalysisServiceV2 = Depends(get_analysis_service),
):
    """
    快速分析

    简化版接口，只需要提供主需求文档即可。

    适用于：
    - 快速评估需求质量
    - 没有辅助文档的场景
    - 原型测试
    """
    try:
        result = await service.analyze_quick(
            primary_markdown_content=request.primary_markdown_content,
            project_id=request.project_id,
            document_id=f"quick-{int(time.time())}",
            document_name=request.document_name,
        )

        return AnalyzeResponse(
            success=True,
            data=result,
            message="快速分析完成"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "分析过程中发生错误",
                "details": {"error": str(e)}
            }
        )


# 导入 time 模块
import time


__all__ = ["router"]
