from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import v1_router
from app.core.logging import setup_logging
from app.core.response import wrap_api_response
from app.seed.init_db import init_db
from app.services import task_service

# 日志在模块导入阶段即初始化，确保 uvicorn worker 启动日志也被捕获
setup_logging()

app = FastAPI(title="AI Testing System API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    recovered_count = task_service.recover_orphaned_requirement_merge_tasks_after_startup()
    if recovered_count:
        logger.warning(
            "Recovered orphaned requirement merge tasks after startup | count={count}",
            count=recovered_count,
        )
    logger.info("Application started — AI Testing System API v0.1.0")


app.middleware("http")(wrap_api_response)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(v1_router, prefix="/api/v1")
