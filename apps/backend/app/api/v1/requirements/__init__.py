"""需求文档（requirement documents）路由统一对外入口。

子模块：
- :mod:`documents` —— 文档 CRUD：列表、创建、上传、追加文件
- :mod:`files` —— 文档下文件操作：追加文件、设置主文件
- :mod:`versions` —— 文档版本管理：版本列表、版本详情、切换当前版本
- :mod:`analysis_runs` —— AI 分析运行：发起审查/分析、停止、列表
- :mod:`analysis` —— AI 分析产物：最终化、初步文档编辑、问答澄清
- :mod:`metadata` —— 元信息：概览、重名检查

每个子路由都各自带完整 prefix ``/projects/{project_id}/requirements``，通过 ``include_router`` 挂到主 router。
``global_router``（prefix ``/requirements``）承载跨项目的"可见需求文档列表"。

URL/方法与重构前完全一致。
"""

from fastapi import APIRouter, Depends

from app.api.v1.requirements import (
    analysis,
    analysis_runs,
    documents,
    files,
    metadata,
    versions,
)
from app.dependencies.auth import current_user
from app.services.document import documents as document_documents

# 占位 router：所有路径都来自子模块，主 router 自身不挂任何路径，仅用于聚合子路由。
# 真实的 prefix 在子模块的 router 上声明。
router = APIRouter()
router.include_router(documents.router)
router.include_router(files.router)
router.include_router(versions.router)
router.include_router(analysis_runs.router)
router.include_router(analysis.router)
router.include_router(metadata.router)


global_router = APIRouter(prefix="/requirements", tags=["requirements"])


@global_router.get("")
def list_visible_requirements(actor=Depends(current_user)) -> list[dict]:
    return document_documents.list_visible_documents(actor)


__all__ = ["router", "global_router"]
