import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.dependencies.auth import current_user, require_admin
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    init_db()


def _seed_observed_case(tmp_path: Path) -> None:
    observation_path = storage.PROJECT_FILE_STORAGE_ROOT / "project-1" / "api_automation" / "runs" / "apirun-1" / "observations.json"
    observation_path.parent.mkdir(parents=True, exist_ok=True)
    observation_path.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "case_id": "apitc-1",
                        "status_code": 400,
                        "response_body": {"code": "INVALID_ARGUMENT", "message": "start_date required"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-1",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/analysis",
            normalized_path="/analysis",
            summary="数据分析",
            description="",
            tags=[],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={},
            created_by=ACTOR["id"],
        )
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-1",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="缺少 start_date",
            priority="P1",
            coverage="negative",
            source="ai_generated",
            preconditions=[],
            request={"method": "POST", "path": "/analysis", "body": {"end_date": "2026-02-05"}},
            test_data={},
            expected={},
            assertions=[],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
            test_point_key="body.required.start_date.missing",
            oracle_status="needs_confirmation",
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-1",
            task_id="api_automation_run:apirun-1",
            project_id="project-1",
            api_environment_id=None,
            script_ids=[],
            command_summary="pytest",
            created_by=ACTOR["id"],
            status="observed",
        )
        api_automation_repo.update_api_run(
            db,
            "apirun-1",
            status="observed",
            observation_result_path=storage.store_path(observation_path) or "",
            summary={"observed": 1},
            finished=True,
        )


def test_create_oracle_proposal_from_observation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)

    proposal = service.create_oracle_proposal("project-1", "apitc-1", "apirun-1", ACTOR)

    assert proposal["status"] == "pending"
    assert proposal["proposed_snapshot"]["oracle_status"] == "confirmed"
    assert proposal["proposed_snapshot"]["assertions"] == [
        {"type": "status_code", "path": "", "expected": 400},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "INVALID_ARGUMENT"},
    ]


def test_create_oracle_proposals_for_run_is_automatic_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)

    first = service.create_oracle_proposals_for_run("apirun-1")
    second = service.create_oracle_proposals_for_run("apirun-1")

    with connect() as db:
        proposals = api_automation_repo.list_oracle_proposals(db, "project-1")

    assert first == {"created": 1, "skipped": 0, "errors": []}
    assert second == {"created": 0, "skipped": 1, "errors": []}
    assert len(proposals) == 1
    assert proposals[0]["created_by"] == "system"


def test_execute_api_run_records_automatic_oracle_proposal_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)
    suite_path = storage.PROJECT_FILE_STORAGE_ROOT / "project-1" / "api_automation" / "pytest_requests"
    test_path = suite_path / "testcases" / "test_analysis.py"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    observation_path = storage.resolve_stored_path(
        next(iter(service.list_api_runs("project-1", ACTOR)["items"]))["observation_result_path"]
    )
    with connect() as db:
        db.execute(
            """
            UPDATE api_automation_runs
            SET target_type = 'scenario', execution_snapshot_json = ?
            WHERE id = 'apirun-1'
            """,
            (
                json.dumps(
                    {
                        "suite_path": storage.store_path(suite_path),
                        "test_file_path": storage.store_path(test_path),
                    }
                ),
            ),
        )
    monkeypatch.setattr(
        service,
        "run_script_suite",
        lambda **kwargs: {
            "status": "observed",
            "summary": {"total": 1, "passed": 1, "failed": 0, "observed": 1},
            "error_message": "",
            "stdout_path": str(tmp_path / "stdout.txt"),
            "stderr_path": str(tmp_path / "stderr.txt"),
            "json_report_path": str(tmp_path / "report.json"),
            "observation_result_path": str(observation_path),
            "exitcode": 0,
        },
    )

    completed = service.execute_api_run("apirun-1")

    assert completed["status"] == "observed"
    assert completed["summary"]["oracle_proposals"] == {"created": 1, "skipped": 0, "errors": []}


def test_oracle_proposal_routes_create_list_approve_and_enforce_project_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-2", "其他项目", ACTOR["id"]),
        )
    from app.main import app

    app.dependency_overrides[current_user] = lambda: ACTOR
    app.dependency_overrides[require_admin] = lambda: ACTOR
    try:
        with TestClient(app) as client:
            created_response = client.post(
                "/api/v1/projects/project-1/api-test-cases/apitc-1/oracle-proposals",
                json={"run_id": "apirun-1"},
            )
            assert created_response.status_code == 200
            proposal = created_response.json()["data"]

            listed_response = client.get("/api/v1/projects/project-1/oracle-proposals?status=pending")
            assert listed_response.status_code == 200
            assert [item["id"] for item in listed_response.json()["data"]] == [proposal["id"]]

            cross_project = client.post(
                f"/api/v1/projects/project-2/oracle-proposals/{proposal['id']}/approve",
                json={"scope": "case_only", "review_comment": "", "assertions": None},
            )
            assert cross_project.status_code == 404

            approved_response = client.post(
                f"/api/v1/projects/project-1/oracle-proposals/{proposal['id']}/approve",
                json={"scope": "case_only", "review_comment": "确认", "assertions": None},
            )
            assert approved_response.status_code == 200
            assert approved_response.json()["data"]["status"] == "approved"

            duplicate_review = client.post(
                f"/api/v1/projects/project-1/oracle-proposals/{proposal['id']}/approve",
                json={"scope": "case_only", "review_comment": "重复", "assertions": None},
            )
            assert duplicate_review.status_code == 409
    finally:
        app.dependency_overrides.pop(current_user, None)
        app.dependency_overrides.pop(require_admin, None)


def test_approve_oracle_proposal_versions_case_and_writes_endpoint_fact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)
    proposal = service.create_oracle_proposal("project-1", "apitc-1", "apirun-1", ACTOR)

    approved = service.approve_oracle_proposal(
        "project-1",
        proposal["id"],
        scope="case_and_endpoint_asset",
        review_comment="确认实际契约",
        assertions=None,
        actor=ACTOR,
    )

    with connect() as db:
        case = api_automation_repo.find_api_test_case(db, "apitc-1")
        versions = api_automation_repo.list_api_test_case_versions(db, "apitc-1")
        facts = api_automation_repo.list_endpoint_oracle_facts(db, "apiend-1")

    assert approved["status"] == "approved"
    assert case["oracle_status"] == "confirmed"
    assert json.loads(case["assertions_json"])[0]["expected"] == 400
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert len(facts) == 1
    assert facts[0]["test_point_key"] == "body.required.start_date.missing"


def test_reject_oracle_proposal_keeps_case_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_observed_case(tmp_path)
    proposal = service.create_oracle_proposal("project-1", "apitc-1", "apirun-1", ACTOR)

    rejected = service.reject_oracle_proposal(
        "project-1",
        proposal["id"],
        review_comment="该响应由测试环境异常导致",
        actor=ACTOR,
    )

    with connect() as db:
        case = api_automation_repo.find_api_test_case(db, "apitc-1")

    assert rejected["status"] == "rejected"
    assert case["oracle_status"] == "needs_confirmation"
    assert json.loads(case["assertions_json"]) == []
