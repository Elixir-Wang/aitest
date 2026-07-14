import sys
from pathlib import Path

sys.path.insert(0, ".")
import pytest
from types import ModuleType, SimpleNamespace

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


import tempfile

data_dir = Path(tempfile.mkdtemp())
project_root = data_dir / "projects"
settings.DATA_DIR = data_dir
settings.DB_PATH = data_dir / "ai_testing.db"
settings.PROJECT_FILE_STORAGE_ROOT = project_root
db_core.DATA_DIR = data_dir
db_core.DB_PATH = data_dir / "ai_testing.db"
storage.PROJECT_FILE_STORAGE_ROOT = project_root
service.collect_script_suite = lambda **kwargs: {"ok": True, "exitcode": 0, "stdout": "", "stderr": ""}
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
        test_data={}, expected={"status_code": 200}, assertions=[{"type": "status_code", "expected": 200}],
        variables={}, data_origin={}, data_file_path="", notes="", created_by=ACTOR["id"],
    )

result = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)
script = result["scripts"][0]
suite_path = Path(storage.resolve_stored_path(script["suite_path"]))
test_file = Path(storage.resolve_stored_path(script["test_file_path"]))
print("test_file:", test_file)
print("exists before delete:", test_file.exists())
print("--- suite tree ---")
for p in sorted(suite_path.rglob("*")):
    print(" ", p)
