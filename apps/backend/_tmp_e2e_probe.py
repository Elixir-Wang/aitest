import os, sys, shutil
from pathlib import Path

sys.path.insert(0, ".")
import tempfile

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import service
from app.services.api_automation import runner

ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}

tmp_root = Path(tempfile.mkdtemp())
project_storage = tmp_root / "projects"
settings.DATA_DIR = tmp_root
settings.DB_PATH = tmp_root / "ai_testing.db"
settings.PROJECT_FILE_STORAGE_ROOT = project_storage
db_core.DATA_DIR = tmp_root
db_core.DB_PATH = tmp_root / "ai_testing.db"
storage.PROJECT_FILE_STORAGE_ROOT = project_storage
init_db()

with connect() as db:
    db.execute(
        "INSERT OR IGNORE INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
        ("project-1", "测试项目", ACTOR["id"]),
    )
    api_automation_repo.upsert_endpoint(
        db, endpoint_id="apiend-1", project_id="project-1", document_id=None,
        method="POST", path="/api/login", normalized_path="/api/login", summary="登录",
        description="", tags=[], parameters=[], request_body={},
        responses={"200": {"description": "success"}}, auth={}, source={"source_type": "manual"},
        created_by=ACTOR["id"],
    )
    api_automation_repo.create_api_test_case(
        db, case_id="apitc-1", project_id="project-1", endpoint_id="apiend-1",
        source_test_case_id=None, generation_run_id=None, title="登录成功", priority="P1",
        coverage="positive", source="manual", preconditions=[],
        request={"method": "POST", "path": "/api/login", "body": {"username": "demo"}},
        test_data={}, expected={"status_code": 200},
        assertions=[{"type": "status_code", "expected": 200}],
        variables={}, data_origin={}, data_file_path="", notes="", created_by=ACTOR["id"],
    )

# 不再 monkeypatch collect_script_suite —— 让它走真子进程
if hasattr(service, "collect_script_suite"):
    pass

result = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)
print("summary:", result["summary"])
print("scripts:", [(s["endpoint_id"], s["name"], s["suite_path"]) for s in result["scripts"]])

# 额外：用 runner.collect_script_suite 跑一次
suite_path = Path(storage.resolve_stored_path(result["suite_path"]))
test_file_path = Path(storage.resolve_stored_path(result["scripts"][0]["test_file_path"]))
rel = test_file_path.relative_to(suite_path).as_posix()
print("relative test path:", rel)
collection = runner.collect_script_suite(suite_path=suite_path, timeout=120, test_paths=[rel])
print("collection.ok:", collection.get("ok"))
print("collection.exitcode:", collection.get("exitcode"))
print("stdout (first 500 chars):", (collection.get("stdout") or "")[:500])
print("stderr (first 500 chars):", (collection.get("stderr") or "")[:500])
