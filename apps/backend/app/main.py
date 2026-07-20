import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import v1_router
from app.core.logging import setup_logging
from app.core.response import ApiResponseMiddleware, ApiUnhandledExceptionMiddleware
from app.seed.init_db import init_db
from app.core.db import connect
from app.services.performance_testing import run_repo
from app.services import task_service, test_case_service, test_point_service
from app.services.api_automation import service as api_automation_service
from app.services.page_exploration import event_bus, page_exploration_service

recover_interrupted_exploration_runs = page_exploration_service.recover_interrupted_exploration_runs

# 日志在模块导入阶段即初始化，确保 uvicorn worker 启动日志也被捕获
setup_logging()

app = FastAPI(title="AI Testing System API", version="0.1.0")

# 默认仅允许本机前端；通过环境变量 CORS_ALLOW_ORIGINS 追加（如内网/演示环境），
# 多个 origin 用英文逗号分隔，例如：
#   CORS_ALLOW_ORIGINS="http://192.168.1.100:3000,http://10.0.0.5:3000"
_default_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://172.16.187.149:3000",
]
_extra_cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]

# Added before CORS so unexpected endpoint failures are converted to responses
# that still pass through the CORS middleware.
app.add_middleware(ApiUnhandledExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=[*_default_cors_origins, *_extra_cors_origins],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    with connect() as db:
        run_repo.recover_stale_runs(db)
    recover_interrupted_exploration_runs()
    task_service.recover_interrupted_requirement_analysis_runs()
    test_case_service.recover_interrupted_test_case_generation_runs()
    test_point_service.recover_interrupted_generation_runs()
    api_automation_service.recover_interrupted_api_automation_tasks()
    logger.info("Application started — AI Testing System API v0.1.0")


@app.on_event("shutdown")
def shutdown() -> None:
    event_bus.close_all()
    # 杀掉所有 browser-session.mjs Node 子进程（正常路径由 runtime_context 关闭，
    # 但 Ctrl+C / kill 时 ContextVar 未执行，需要兜底）
    import subprocess, sys
    try:
        result = subprocess.run(
            [
                sys.executable, "-c",
                "import subprocess, sys; "
                "procs = subprocess.run(['powershell', '-Command', "
                "'Get-CimInstance Win32_Process | Where-Object { $_.Name -eq \"node.exe\" -and $_.CommandLine -like \"*browser-session*\" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'], "
                "capture_output=True, text=True)"
            ],
            capture_output=True,
            text=True,
        )
    except Exception:
        pass
    logger.info("Application shutdown signal handled")


app.add_middleware(ApiResponseMiddleware)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(v1_router, prefix="/api/v1")
