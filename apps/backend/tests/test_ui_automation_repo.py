import sqlite3

from app.repositories import ui_automation_repo


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(ui_automation_repo.SCHEMA_SQL)
    return db


def test_generation_run_and_asset_round_trip():
    db = _db()
    ui_automation_repo.create_generation_run(
        db,
        run_id="uigen-1",
        project_id="project-1",
        test_case_id="case-1",
        manual_test_case_id=None,
        environment_id="env-1",
        exploration_run_id="explore-1",
        created_by="user-1",
    )
    ui_automation_repo.update_generation_run(
        db,
        "uigen-1",
        status="completed",
        suite_path="project-1/ui_automation/pytest_playwright",
        changed_files=["testcases/generated/test_login.py"],
    )
    ui_automation_repo.upsert_asset(
        db,
        asset_id="uiasset-1",
        project_id="project-1",
        test_case_id="case-1",
        manual_test_case_id=None,
        source_version=1,
        generation_run_id="uigen-1",
        status="ready",
        pytest_node_id="testcases/generated/test_login.py::test_uiauto_1",
        suite_path="project-1/ui_automation/pytest_playwright",
        test_file_path="testcases/generated/test_login.py",
        data_file_path="data/cases/login.yaml",
        plan_file_path="data/cases/login.plan.json",
        source_hash="hash-1",
        created_by="user-1",
    )

    run = ui_automation_repo.find_generation_run(db, "uigen-1")
    generation_runs = ui_automation_repo.list_generation_runs(db, "project-1")
    asset = ui_automation_repo.find_asset(db, "uiasset-1")

    assert run["status"] == "completed"
    assert run["changed_files_json"] == '["testcases/generated/test_login.py"]'
    assert [row["id"] for row in generation_runs] == ["uigen-1"]
    assert asset["pytest_node_id"].endswith("::test_uiauto_1")


def test_delete_execution_run_removes_record():
    db = _db()
    ui_automation_repo.create_execution_run(
        db,
        run_id="uirun-1",
        project_id="project-1",
        asset_id="uiasset-1",
        environment_id="env-1",
        created_by="user-1",
    )

    ui_automation_repo.delete_execution_run(db, "uirun-1")

    assert ui_automation_repo.find_execution_run(db, "uirun-1") is None
