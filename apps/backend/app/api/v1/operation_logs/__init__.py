"""操作日志（operation logs）路由统一对外入口。

子模块：
- :mod:`query` —— 全局日志查询 / 详情 / CSV 导出 / 过滤项
- :mod:`retention` —— 保留策略读取 / 更新 / 清理
- :mod:`client_errors` —— 前端客户端错误上报
- :mod:`project_query` —— 项目级日志查询 / CSV 导出 / 过滤项

每个子模块自带完整 prefix 和统一 tag ``operation-logs``。主 ``router`` / ``project_router``
不带 prefix，仅做 ``include_router`` 聚合。URL/方法与重构前完全一致。
"""

from fastapi import APIRouter

from app.api.v1.operation_logs import client_errors, project_query, query, retention

router = APIRouter()
router.include_router(query.router)
router.include_router(retention.router)
router.include_router(client_errors.router)

project_router = APIRouter()
project_router.include_router(project_query.router)


__all__ = ["router", "project_router"]


# 注：原 ``operation_logs.py`` 中 ``list_logs`` 与 ``list_project_logs`` 在 ``OperationLogQuery``
# 构造时有 ``from app.schemas.operation_log import OperationLogQuery`` 的局部 import，
# 拆包后已在子模块顶部集中导入，消除局部 import 带来的重复解析开销。
