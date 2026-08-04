import json
import shutil

import yaml

from app.core import db as core_db
from app.repositories import ui_automation_repo
from app.seed.init_db import init_db
from app.services.ui_automation import service
from app.services.ui_automation.revision import repair_business_step_mapping


ACTOR = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _seed_revision_asset(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()
    suite_path = tmp_path / "suite"
    test_path = suite_path / "testcases/generated/project_1/test_login.py"
    data_path = suite_path / "data/projects/project_1/cases/login.yaml"
    plan_path = suite_path / "data/projects/project_1/cases/login.plan.json"
    test_path.parent.mkdir(parents=True)
    data_path.parent.mkdir(parents=True)
    test_path.write_text("def test_uiauto_1():\n    pass\n", encoding="utf-8")
    data_path.write_text("schema_version: v2\n", encoding="utf-8")
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "v2",
                "project_id": "project-1",
                "automation_case_id": "uiauto-1",
                "source_test_case_id": "manual-1",
                "source_test_case_version": 1,
                "environment_id": "env-1",
                "exploration_run_id": "",
                "page_objects": [],
                "steps": [{"source_step_id": "step-1", "kind": "navigate", "page_key": "login"}],
                "assertions": [],
                "artifacts": {
                    "test_file": "testcases/generated/project_1/test_login.py",
                    "data_file": "data/projects/project_1/cases/login.yaml",
                    "plan_file": "data/projects/project_1/cases/login.plan.json",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with core_db.connect() as db:
        db.execute("INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')")
        db.execute(
            "INSERT INTO project_environments (id, project_id, name, site_url, created_by) VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')"
        )
        db.execute(
            """
            INSERT INTO manual_test_cases (id, project_id, title, steps_json, created_by)
            VALUES ('manual-1', 'project-1', '登录流程', ?, 'u-admin')
            """,
            (json.dumps([{"action": "进入登录页"}], ensure_ascii=False),),
        )
        ui_automation_repo.create_generation_run(
            db,
            run_id="uigen-base",
            project_id="project-1",
            test_case_id=None,
            manual_test_case_id="manual-1",
            environment_id="env-1",
            exploration_run_id="",
            created_by="u-admin",
        )
        ui_automation_repo.update_generation_run(db, "uigen-base", status="completed")
        ui_automation_repo.upsert_asset(
            db,
            asset_id="uiasset-1",
            project_id="project-1",
            test_case_id=None,
            manual_test_case_id="manual-1",
            source_version=1,
            generation_run_id="uigen-base",
            status="ready",
            pytest_node_id="testcases/generated/project_1/test_login.py::test_uiauto_1",
            suite_path=str(suite_path),
            test_file_path="testcases/generated/project_1/test_login.py",
            data_file_path="data/projects/project_1/cases/login.yaml",
            plan_file_path="data/projects/project_1/cases/login.plan.json",
            source_hash="hash-1",
            created_by="u-admin",
        )
    monkeypatch.setattr(service, "_ensure_project_suite_migrated", lambda project_id: suite_path)
    monkeypatch.setattr(service, "project_suite_path", lambda project_id: suite_path)
    return suite_path, plan_path


def test_repair_business_step_mapping_groups_operations_without_changing_behavior():
    plan = {
        "schema_version": "v2",
        "steps": [
            {
                "source_step_id": "step-1",
                "business_step_id": "",
                "title": "",
                "action": "click",
                "locator": {"role": "button", "name": "开始"},
                "assertion": {"text": "工作台"},
            },
            {
                "source_step_id": "step-1-send",
                "business_step_id": "",
                "title": "",
                "action": "click",
                "locator": {"role": "button", "name": "发送"},
                "assertion": {"text": "已发送"},
            },
            {
                "source_step_id": "step-2",
                "business_step_id": "",
                "title": "",
                "action": "wait",
                "locator": {"role": "status", "name": "回复"},
                "assertion": {"text": "完成"},
            },
        ],
    }
    case_data = {
        "steps": [
            {"id": "step-1", "action": "发送消息"},
            {"id": "step-2", "action": "等待回复"},
        ]
    }

    repaired = repair_business_step_mapping(plan, case_data)

    assert repaired["schema_version"] == "v2"
    assert [step["business_step_id"] for step in repaired["steps"]] == ["step-1", "step-1", "step-2"]
    assert [step["title"] for step in repaired["steps"]] == ["发送消息", "发送消息", "等待回复"]
    assert repaired["steps"][0]["locator"] == plan["steps"][0]["locator"]
    assert repaired["steps"][1]["assertion"] == plan["steps"][1]["assertion"]


def test_repair_business_step_mapping_returns_none_for_unmapped_or_ambiguous_operations():
    plan = {"schema_version": "v2", "steps": [{"source_step_id": "step-99", "action": "click"}]}
    case_data = {"steps": [{"id": "step-1", "action": "开始"}]}

    assert repair_business_step_mapping(plan, case_data) is None


def test_execute_revision_repairs_plan_and_updates_same_asset(monkeypatch, tmp_path):
    suite_path, plan_path = _seed_revision_asset(monkeypatch, tmp_path)

    created = service.create_revision_run(
        "project-1",
        "uiasset-1",
        {"reason_code": "missing_business_step_mapping", "instruction": "", "run_after_revision": True},
        ACTOR,
    )
    def collect_with_runtime_artifacts(workspace, *args, **kwargs):
        cache_file = workspace / ".pytest_cache/v/cache/nodeids"
        bytecode_file = workspace / "testcases/generated/project_1/__pycache__/test_login.pyc"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        bytecode_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("[]", encoding="utf-8")
        bytecode_file.write_bytes(b"bytecode")
        return {"ok": True, "stderr": ""}

    monkeypatch.setattr(service, "collect_suite", collect_with_runtime_artifacts)
    scheduled = []
    monkeypatch.setattr(service, "schedule_execution_run", scheduled.append)

    completed = service.execute_generation_run(created["id"])

    assert completed["status"] == "completed"
    assert completed["revision_strategy"] == "deterministic"
    with core_db.connect() as db:
        asset = ui_automation_repo.find_asset(db, "uiasset-1")
        assert asset["id"] == "uiasset-1"
        assert asset["source_version"] == 2
        assert asset["generation_run_id"] == created["id"]
        execution_runs = ui_automation_repo.list_execution_runs(db, "project-1", "uiasset-1")
        assert len(execution_runs) == 1
        assert execution_runs[0]["id"] == scheduled[0]
    revised_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert revised_plan["schema_version"] == "v2"
    assert revised_plan["steps"][0]["business_step_id"] == "step-1"
    assert revised_plan["steps"][0]["title"] == "进入登录页"
    assert not (suite_path / ".pytest_cache").exists()
    assert not (suite_path / "testcases/generated/project_1/__pycache__").exists()


def test_execute_revision_validation_failure_preserves_formal_asset(monkeypatch, tmp_path):
    suite_path, plan_path = _seed_revision_asset(monkeypatch, tmp_path)
    original_plan = plan_path.read_bytes()
    created = service.create_revision_run(
        "project-1",
        "uiasset-1",
        {"reason_code": "missing_business_step_mapping", "instruction": ""},
        ACTOR,
    )
    monkeypatch.setattr(
        service,
        "collect_suite",
        lambda *args, **kwargs: {"ok": False, "stderr": "collection failed"},
    )

    failed = service.execute_generation_run(created["id"])

    assert failed["status"] == "failed"
    assert "collection failed" in failed["error_message"]
    assert plan_path.read_bytes() == original_plan
    with core_db.connect() as db:
        asset = ui_automation_repo.find_asset(db, "uiasset-1")
        assert asset["source_version"] == 1
        assert asset["generation_run_id"] == "uigen-base"
        assert ui_automation_repo.list_execution_runs(db, "project-1", "uiasset-1") == []
    assert not (suite_path.parent / f".{suite_path.name}.generation-staging" / created["id"]).exists()


def test_execute_revision_missing_formal_suite_marks_run_failed(monkeypatch, tmp_path):
    suite_path, _ = _seed_revision_asset(monkeypatch, tmp_path)
    created = service.create_revision_run(
        "project-1",
        "uiasset-1",
        {"reason_code": "missing_business_step_mapping", "instruction": ""},
        ACTOR,
    )
    shutil.rmtree(suite_path)

    failed = service.execute_generation_run(created["id"])

    assert failed["status"] == "failed"
    assert failed["finished_at"]
    assert failed["error_message"]


def test_execute_mapping_revision_with_instruction_still_uses_deterministic_repair(monkeypatch, tmp_path):
    suite_path, plan_path = _seed_revision_asset(monkeypatch, tmp_path)
    created = service.create_revision_run(
        "project-1",
        "uiasset-1",
        {"reason_code": "missing_business_step_mapping", "instruction": "补充步骤信息"},
        ACTOR,
    )
    async def unexpected_ai_revision(**kwargs):
        raise AssertionError("deterministic mapping repair must run before AI revision")

    monkeypatch.setattr(service, "generate_pytest_playwright_case", unexpected_ai_revision)
    monkeypatch.setattr(service, "collect_suite", lambda *args, **kwargs: {"ok": True, "stderr": ""})

    completed = service.execute_generation_run(created["id"])

    assert completed["status"] == "completed"
    assert completed["revision_strategy"] == "deterministic"
    revised_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert revised_plan["steps"][0]["business_step_id"] == "step-1"
    assert revised_plan["steps"][0]["title"] == "进入登录页"


def test_execute_mapping_revision_uses_asset_step_ids_when_current_case_was_reordered(
    monkeypatch, tmp_path
):
    suite_path, plan_path = _seed_revision_asset(monkeypatch, tmp_path)
    data_path = suite_path / "data/projects/project_1/cases/login.yaml"
    data_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "v2",
                "steps": [
                    {"id": "step-1", "action": "进入登录页"},
                    {"id": "step-3", "action": "提交登录"},
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["steps"] = [{"source_step_id": "step-3", "kind": "navigate", "page_key": "login"}]
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    with core_db.connect() as db:
        db.execute(
            "UPDATE manual_test_cases SET steps_json = ? WHERE id = 'manual-1'",
            (json.dumps([{"action": "进入登录页"}, {"action": "提交登录"}], ensure_ascii=False),),
        )

    created = service.create_revision_run(
        "project-1",
        "uiasset-1",
        {"reason_code": "missing_business_step_mapping", "instruction": "补充业务步骤"},
        ACTOR,
    )
    monkeypatch.setattr(service, "collect_suite", lambda *args, **kwargs: {"ok": True, "stderr": ""})

    completed = service.execute_generation_run(created["id"])

    assert completed["status"] == "completed"
    assert completed["revision_strategy"] == "deterministic"
    revised_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert revised_plan["steps"][0]["business_step_id"] == "step-3"
    assert revised_plan["steps"][0]["title"] == "提交登录"
