"""页面探索子路由统一对外入口。

各业务子路由见 :mod:`runs`, :mod:`pages`, :mod:`artifacts`, :mod:`events`，
所有子路由都挂在同一个 ``router``（prefix ``/page-exploration``，tag ``page-exploration``）下，
URL / 标签 / 方法与重构前完全一致。
"""

from fastapi import APIRouter

from app.api.v1.page_exploration import artifacts, events, pages, runs

router = APIRouter(prefix="/page-exploration", tags=["page-exploration"])
router.include_router(runs.router)
router.include_router(pages.router)
router.include_router(artifacts.router)
router.include_router(events.router)

__all__ = ["router"]