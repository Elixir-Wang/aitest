import asyncio
from pathlib import Path

import pytest

from app.agents.model_selection import ModelSelection
from app.agents.api_automation.case_generation.schemas import ApiAutomationGenerationResult, ApiGeneratedCase
from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiAutomationGenerateIn
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def test_generated_case_schema_does_not_expose_tags() -> None:
    assert "tags" not in ApiGeneratedCase.model_fields


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


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


def _seed_project_endpoint() -> None:
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
            path="/login",
            normalized_path="/login",
            summary="登录",
            description="",
            tags=["auth"],
            parameters=[],
            request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )


def _seed_project_endpoint_with_response_schema() -> None:
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
            summary="智能体数据分析",
            description="",
            tags=["analysis"],
            parameters=[],
            request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
            responses={
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string",
                                        "description": '返回码，"000000" 表示成功',
                                        "example": "000000",
                                    },
                                    "data": {
                                        "type": "object",
                                        "properties": {"user_cnt": {"type": "number"}},
                                    },
                                },
                            }
                        }
                    }
                }
            },
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )


def _seed_additional_endpoints(endpoint_ids: list[str]) -> None:
    with connect() as db:
        for endpoint_id in endpoint_ids:
            api_automation_repo.upsert_endpoint(
                db,
                endpoint_id=endpoint_id,
                project_id="project-1",
                document_id=None,
                method="GET",
                path=f"/{endpoint_id}",
                normalized_path=f"/{endpoint_id}",
                summary=endpoint_id,
                description="",
                tags=[],
                parameters=[],
                request_body={},
                responses={"200": {"description": "ok"}},
                auth={},
                source={"source_type": "manual"},
                created_by=ACTOR["id"],
            )


def test_execute_generation_run_limits_concurrency_and_keeps_partial_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    endpoint_ids = ["apiend-1", *[f"apiend-{index}" for index in range(2, 13)]]
    _seed_additional_endpoints(endpoint_ids[1:])
    active_calls = 0
    max_active_calls = 0
    calls: dict[str, int] = {}

    async def fake_generate_api_test_cases(input_data):
        nonlocal active_calls, max_active_calls
        endpoint = input_data.endpoints[0]
        endpoint_id = endpoint["id"]
        calls[endpoint_id] = calls.get(endpoint_id, 0) + 1
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await asyncio.sleep(0.01)
        active_calls -= 1
        if endpoint_id == "apiend-7":
            raise RuntimeError("model failed")
        return ApiAutomationGenerationResult(
            summary="生成 1 条",
            cases=[
                ApiGeneratedCase(
                    title=f"{endpoint_id} success",
                    endpoint_id=endpoint_id,
                    test_point_key="success.minimum_valid",
                    oracle_status="confirmed",
                    request={"method": endpoint["method"], "path": endpoint["path"]},
                    assertions=[{"type": "status_code", "expected": 200}],
                )
            ],
        )

    monkeypatch.setattr(service.api_generation_agent_service, "generate_api_test_cases", fake_generate_api_test_cases)
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=endpoint_ids, generate_code=False),
        ACTOR,
    )

    result = service.execute_generation_run(created["id"])

    with connect() as db:
        items = api_automation_repo.list_generation_items(db, created["id"])
        cases = api_automation_repo.list_api_test_cases(db, "project-1")

    assert max_active_calls == 5
    assert result["status"] == "partial_success"
    assert sum(item["status"] == "completed" for item in items) == 11
    assert sum(item["status"] == "failed" for item in items) == 1
    assert len(cases) == 11
    assert calls["apiend-7"] == 1


def test_generation_item_validation_is_atomic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    async def fake_generate_api_test_cases(input_data):
        return ApiAutomationGenerationResult(
            summary="one invalid",
            cases=[
                ApiGeneratedCase(
                    title="valid",
                    endpoint_id="apiend-1",
                    test_point_key="success.minimum_valid",
                    oracle_status="confirmed",
                    request={"method": "POST", "path": "/login"},
                    assertions=[{"type": "status_code", "expected": 200}],
                ),
                ApiGeneratedCase(
                    title="invalid",
                    endpoint_id="apiend-other",
                    test_point_key="unexpected.point",
                    oracle_status="confirmed",
                    request={"method": "POST", "path": "/login"},
                    assertions=[{"type": "status_code", "expected": 200}],
                ),
            ],
        )

    monkeypatch.setattr(service.api_generation_agent_service, "generate_api_test_cases", fake_generate_api_test_cases)
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    result = service.execute_generation_run(created["id"])

    with connect() as db:
        cases = api_automation_repo.list_api_test_cases(db, "project-1")
    assert result["status"] == "failed"
    assert cases == []


def test_generation_normalizes_body_for_missing_request_body_point(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    # The seeded endpoint only plans a success point, so add the missing-body
    # point directly to exercise the persistence boundary's normalization.
    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        attempt_id = "attempt-normalize"
        api_automation_repo.start_generation_item_attempt(db, item["id"], attempt_id)
        count = service._persist_generation_item_cases(
            db,
            created["id"],
            item["id"],
            attempt_id,
            ApiAutomationGenerationResult(
                summary="生成 2 条",
                cases=[
                    ApiGeneratedCase(
                        title="登录成功",
                        endpoint_id="apiend-1",
                        test_point_key="success.minimum_valid",
                        oracle_status="confirmed",
                        coverage="positive",
                        request={"method": "POST", "path": "/login"},
                        assertions=[{"type": "status_code", "expected": 200}],
                    ),
                    ApiGeneratedCase(
                        title="请求体缺失",
                        endpoint_id="apiend-1",
                        test_point_key="request_body.missing",
                        oracle_status="needs_confirmation",
                        coverage="negative",
                        request={"method": "POST", "path": "/login", "body": {}},
                        assertions=[],
                    ),
                ],
            ),
            planned_test_points=[
                {"key": "success.minimum_valid", "oracle_status": "confirmed"},
                {"key": "request_body.missing", "oracle_status": "needs_confirmation"},
            ],
        )
        rows = api_automation_repo.list_api_test_cases(db, "project-1")

    assert count == 2
    missing_body_rows = [row for row in rows if row["test_point_key"] == "request_body.missing"]
    assert len(missing_body_rows) == 1
    assert "body" not in api_automation_repo.loads_json(missing_body_rows[0]["request_json"], {})


def test_execute_generation_run_saves_generated_cases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    async def fake_generate_api_test_cases(input_data):
        return ApiAutomationGenerationResult(
            summary="生成 1 条",
            cases=[
                ApiGeneratedCase(
                    title="登录成功",
                    priority="P1",
                    endpoint_id="apiend-1",
                    test_point_key="success.minimum_valid",
                    oracle_status="confirmed",
                    request={"method": "POST", "path": "/login", "body": {"username": "demo", "password": "demo"}},
                    test_data={
                        "username": {"value": "demo", "source": "openapi_example", "required": True},
                        "password": {"value": "demo", "source": "openapi_example", "required": True},
                    },
                    assertions=[{"type": "status_code", "expected": 200}],
                ),
            ],
        )

    monkeypatch.setattr(service.api_generation_agent_service, "generate_api_test_cases", fake_generate_api_test_cases)

    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generation_goal="覆盖登录", generate_code=False),
        ACTOR,
    )
    result = service.execute_generation_run(created["id"])

    with connect() as db:
        run = api_automation_repo.find_generation_run(db, created["id"])
        cases = api_automation_repo.list_api_test_cases(db, "project-1")

    assert result["status"] == "completed"
    assert run["status"] == "completed"
    assert len(cases) == 1
    serialized_cases = service.list_api_test_cases("project-1", ACTOR)
    success_case = serialized_cases[0]
    assert success_case["coverage"] == "positive"
    assert success_case["preconditions"] == []
    assert success_case["test_data"]["username"]["source"] == "openapi_example"
    assert "data_origin" not in success_case
    assert "status" not in success_case
    assert api_automation_repo.loads_json(run["result_summary_json"], {})["test_case_count"] == 1


def test_delete_api_test_case_removes_generated_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    with connect() as db:
        case_id = api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-delete",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="登录成功",
            priority="P1",
            coverage="positive",
            source="ai_generated",
            preconditions=[],
            request={"method": "POST", "path": "/login"},
            test_data={},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )

    service.delete_api_test_case("project-1", case_id, ACTOR)

    with connect() as db:
        assert api_automation_repo.find_api_test_case(db, case_id) is None


def test_get_api_test_case_returns_structured_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    with connect() as db:
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-detail",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="登录成功",
            priority="P1",
            coverage="positive",
            source="ai_generated",
            preconditions=["用户账号存在"],
            request={"method": "POST", "path": "/login"},
            test_data={"username": {"value": "demo", "source": "openapi_example", "required": True}},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={"test_data.username": "openapi_example"},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )

    detail = service.get_api_test_case("project-1", "apitc-detail", ACTOR)

    assert detail["id"] == "apitc-detail"
    assert detail["coverage"] == "positive"
    assert detail["preconditions"] == ["用户账号存在"]
    assert detail["test_data"]["username"]["value"] == "demo"
    assert "source" not in detail
    assert "tags" not in detail
    assert "data_origin" not in detail


def test_execute_generation_run_passes_source_test_cases_to_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    captured = {}

    with connect() as db:
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("doc-1", "project-1", "登录需求", "requirement", "finalized", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO test_case_sets (
              id, project_id, name, requirement_doc_id, generation_scope_type,
              generation_scope_text, notes, status, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("set-1", "project-1", "登录用例", "doc-1", "all", "", "", "ready_for_review", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO test_cases (
              id, test_case_set_id, project_id, title, module, priority, preconditions,
              steps_json, expected_result, source_requirement_refs, source_exploration_refs, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "tc-001",
                "set-1",
                "project-1",
                "登录成功",
                "登录",
                "P1",
                "用户账号存在",
                '[{"action":"调用登录接口","expected_result":"返回登录成功"}]',
                "返回登录成功",
                "[]",
                "[]",
                "approved",
            ),
        )

    async def fake_generate_api_test_cases(input_data):
        captured["source_test_cases"] = input_data.source_test_cases
        return ApiAutomationGenerationResult(summary="生成 0 条", cases=[])

    monkeypatch.setattr(service.api_generation_agent_service, "generate_api_test_cases", fake_generate_api_test_cases)

    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], test_case_ids=["tc-001"], generate_code=False),
        ACTOR,
    )

    service.execute_generation_run(created["id"])

    assert captured["source_test_cases"][0]["id"] == "tc-001"
    assert captured["source_test_cases"][0]["steps"][0]["action"] == "调用登录接口"


def test_generation_input_applies_approved_endpoint_oracle_fact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )
    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        api_automation_repo.upsert_endpoint_oracle_fact(
            db,
            fact_id="apifact-1",
            endpoint_id="apiend-1",
            test_point_key="success.minimum_valid",
            assertions=[{"type": "status_code", "path": "", "expected": 201}],
            evidence_run_ids=["apirun-1"],
            approved_by=ACTOR["id"],
        )
        input_data = service._build_generation_item_input(db, created["id"], item["id"])

    planned_point = next(point for point in input_data.planned_test_points if point["key"] == "success.minimum_valid")
    assert planned_point["oracle_status"] == "confirmed"
    assert planned_point["assertions"] == [{"type": "status_code", "path": "", "expected": 201}]
    assert planned_point["oracle_fact"] == {
        "approved_by": ACTOR["id"],
        "evidence_run_ids": ["apirun-1"],
    }


def test_generation_input_adds_required_response_contract_assertions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_with_response_schema()
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        input_data = service._build_generation_item_input(db, created["id"], item["id"])

    planned_point = next(point for point in input_data.planned_test_points if point["key"] == "success.minimum_valid")
    assert planned_point["required_assertions"] == [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "content_type", "path": "", "expected": "application/json"},
        {"type": "jsonpath_exists", "path": "$.code", "expected": True},
        {"type": "jsonpath_type", "path": "$.code", "expected": "string"},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
        {"type": "jsonpath_exists", "path": "$.data", "expected": True},
        {"type": "jsonpath_type", "path": "$.data", "expected": "object"},
        {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
        {"type": "jsonpath_type", "path": "$.data.user_cnt", "expected": "number"},
    ]


def test_persist_generation_item_cases_completes_missing_response_contract_assertions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_with_response_schema()
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        input_data = service._build_generation_item_input(db, created["id"], item["id"])
        attempt_id = "attempt-response-contract"
        api_automation_repo.start_generation_item_attempt(db, item["id"], attempt_id)
        count = service._persist_generation_item_cases(
            db,
            created["id"],
            item["id"],
            attempt_id,
            ApiAutomationGenerationResult(
                summary="生成 1 条",
                cases=[
                    ApiGeneratedCase(
                        title="分析成功",
                        endpoint_id="apiend-1",
                        test_point_key="success.minimum_valid",
                        oracle_status="confirmed",
                        coverage="positive",
                        request={"method": "POST", "path": "/analysis"},
                        assertions=[{"type": "status_code", "expected": 200}],
                    )
                ],
            ),
            planned_test_points=input_data.planned_test_points,
        )
        rows = api_automation_repo.list_api_test_cases(db, "project-1")

    assert count == 1
    assert api_automation_repo.loads_json(rows[0]["assertions_json"], []) == [
        {"type": "status_code", "path": "", "expected": 200},
        {"type": "content_type", "path": "", "expected": "application/json"},
        {"type": "jsonpath_exists", "path": "$.code", "expected": True},
        {"type": "jsonpath_type", "path": "$.code", "expected": "string"},
        {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"},
        {"type": "jsonpath_exists", "path": "$.data", "expected": True},
        {"type": "jsonpath_type", "path": "$.data", "expected": "object"},
        {"type": "jsonpath_exists", "path": "$.data.user_cnt", "expected": True},
        {"type": "jsonpath_type", "path": "$.data.user_cnt", "expected": "number"},
    ]


def test_persist_generation_item_cases_corrects_fixed_success_code_for_boundary_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint_with_response_schema()
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        attempt_id = "attempt-boundary-success-contract"
        api_automation_repo.start_generation_item_attempt(db, item["id"], attempt_id)
        service._persist_generation_item_cases(
            db,
            created["id"],
            item["id"],
            attempt_id,
            ApiAutomationGenerationResult(
                summary="生成 1 条",
                cases=[
                    ApiGeneratedCase(
                        title="单日范围查询",
                        endpoint_id="apiend-1",
                        test_point_key="body.date_relation.start_equals_end",
                        oracle_status="needs_confirmation",
                        coverage="boundary",
                        request={"method": "POST", "path": "/analysis"},
                        assertions=[
                            {"type": "status_code", "expected": 200},
                            {"type": "jsonpath_equals", "path": "$.code", "expected": 0},
                        ],
                    )
                ],
            ),
            planned_test_points=[
                {
                    "key": "body.date_relation.start_equals_end",
                    "oracle_status": "needs_confirmation",
                }
            ],
        )
        rows = api_automation_repo.list_api_test_cases(db, "project-1")

    assertions = api_automation_repo.loads_json(rows[0]["assertions_json"], [])
    assert {"type": "jsonpath_equals", "path": "$.code", "expected": "000000"} in assertions
    assert {"type": "jsonpath_equals", "path": "$.code", "expected": 0} not in assertions


def test_generation_skills_require_backend_response_contract_assertions() -> None:
    root = Path(__file__).resolve().parents[1]
    case_generation_skill = (
        root
        / "app"
        / "agents"
        / "api_automation"
        / "case_generation"
        / "skills"
        / "api-automation-case-generation"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assertion_guidelines = (
        root
        / "app"
        / "agents"
        / "api_automation"
        / "case_generation"
        / "skills"
        / "api-automation-case-generation"
        / "references"
        / "assertion-guidelines.md"
    ).read_text(encoding="utf-8")
    pytest_generation_skill = (
        root
        / "app"
        / "agents"
        / "api_automation"
        / "pytest_requests"
        / "skills"
        / "pytest-requests-code-generation"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assertion_mapping = (
        root
        / "app"
        / "agents"
        / "api_automation"
        / "pytest_requests"
        / "skills"
        / "pytest-requests-code-generation"
        / "references"
        / "assertion-mapping.md"
    ).read_text(encoding="utf-8")

    assert "required_assertions" in case_generation_skill
    assert "不得删除、修改或弱化" in case_generation_skill
    assert "必须生成 `jsonpath_exists`" in assertion_guidelines
    assert "已明确的响应契约断言" in pytest_generation_skill
    assert "jsonpath_exists" in assertion_mapping


def test_generation_run_serializes_items_and_retries_only_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    _seed_additional_endpoints(["apiend-2", "apiend-3"])
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1", "apiend-2", "apiend-3"], generate_code=False),
        ACTOR,
    )

    with connect() as db:
        items = api_automation_repo.list_generation_items(db, created["id"])
        api_automation_repo.start_generation_item_attempt(db, items[0]["id"], "attempt-success")
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-success",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=created["id"],
            generation_item_id=items[0]["id"],
            generation_attempt_id="attempt-success",
            title="登录成功",
            priority="P1",
            coverage="positive",
            source="ai_generated",
            preconditions=[],
            request={"method": "POST", "path": "/login"},
            test_data={},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )
        api_automation_repo.finish_generation_item_attempt(
            db, items[0]["id"], "attempt-success", status="completed", generated_case_count=1
        )
        for index, item in enumerate(items[1:], start=2):
            attempt_id = f"attempt-failed-{index}"
            api_automation_repo.start_generation_item_attempt(db, item["id"], attempt_id)
            api_automation_repo.finish_generation_item_attempt(
                db, item["id"], attempt_id, status="failed", error_message=f"failure-{index}"
            )
        api_automation_repo.update_generation_run(db, created["id"], status="partial_success", finished=True)

    detail = service.get_generation_run("project-1", created["id"], ACTOR)

    assert detail["total_count"] == 3
    assert detail["completed_count"] == 3
    assert detail["success_count"] == 1
    assert detail["failed_count"] == 2
    assert detail["generated_case_count"] == 1
    assert [(item["method"], item["path"]) for item in detail["items"]] == [
        ("POST", "/login"),
        ("GET", "/apiend-2"),
        ("GET", "/apiend-3"),
    ]
    assert detail["items"][0]["attempts"][0]["id"] == "attempt-success"
    assert [case["id"] for case in detail["test_cases"]] == ["apitc-success"]

    retried = service.retry_failed_generation_items("project-1", created["id"], ACTOR)

    assert retried["status"] == "running"
    assert retried["finished_at"] is None
    with connect() as db:
        refreshed_items = api_automation_repo.list_generation_items(db, created["id"])
        cases = api_automation_repo.list_api_test_cases(db, "project-1")
    assert refreshed_items[0]["status"] == "completed"
    assert refreshed_items[0]["attempt_count"] == 1
    assert [item["status"] for item in refreshed_items[1:]] == ["queued", "queued"]
    assert [item["attempt_count"] for item in refreshed_items[1:]] == [1, 1]
    assert [case["id"] for case in cases] == ["apitc-success"]


def test_retry_failed_generation_items_rejects_active_or_successful_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1"], generate_code=False),
        ACTOR,
    )

    with pytest.raises(Exception) as active_error:
        service.retry_failed_generation_items("project-1", created["id"], ACTOR)
    assert active_error.value.status_code == 409

    with connect() as db:
        item = api_automation_repo.list_generation_items(db, created["id"])[0]
        api_automation_repo.start_generation_item_attempt(db, item["id"], "attempt-success")
        api_automation_repo.finish_generation_item_attempt(
            db, item["id"], "attempt-success", status="completed", generated_case_count=0
        )
        api_automation_repo.update_generation_run(db, created["id"], status="completed", finished=True)

    with pytest.raises(Exception) as completed_error:
        service.retry_failed_generation_items("project-1", created["id"], ACTOR)
    assert completed_error.value.status_code == 409


def test_recovery_preserves_completed_generation_items(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    _seed_additional_endpoints(["apiend-2"])
    created = service.create_generation_run(
        "project-1",
        ApiAutomationGenerateIn(endpoint_ids=["apiend-1", "apiend-2"], generate_code=False),
        ACTOR,
    )

    with connect() as db:
        items = api_automation_repo.list_generation_items(db, created["id"])
        api_automation_repo.start_generation_item_attempt(db, items[0]["id"], "attempt-success")
        api_automation_repo.finish_generation_item_attempt(
            db, items[0]["id"], "attempt-success", status="completed", generated_case_count=1
        )
        api_automation_repo.start_generation_item_attempt(db, items[1]["id"], "attempt-running")
        api_automation_repo.update_generation_run(db, created["id"], status="running")

    service.recover_interrupted_api_automation_tasks()

    with connect() as db:
        run = api_automation_repo.find_generation_run(db, created["id"])
        items = api_automation_repo.list_generation_items(db, created["id"])
        attempts = api_automation_repo.list_generation_item_attempts(db, items[1]["id"])
    assert run["status"] == "partial_success"
    assert "失败接口可重试" in run["error_message"]
    assert items[0]["status"] == "completed"
    assert items[1]["status"] == "failed"
    assert attempts[0]["status"] == "failed"


def test_api_automation_agent_uses_skill_middleware_and_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.api_automation.case_generation import agent as agent_module

    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "agent"

    monkeypatch.setattr(agent_module, "create_agent", fake_create_agent)

    created = agent_module.api_automation_generation_agent("model")

    assert created == "agent"
    assert captured["model"] == "model"
    assert captured["tools"] == []
    assert captured["middleware"][0].name == "SkillMiddleware"
    assert captured["middleware"][1].name == "InvalidToolCallRecoveryMiddleware"
    assert "api-automation-case-generation" in str(captured["middleware"][0].skill_path)
    assert isinstance(captured["response_format"], ToolStrategy)
    assert captured["response_format"].schema is ApiAutomationGenerationResult
    assert captured["response_format"].handle_errors is True


@pytest.mark.anyio
async def test_api_automation_agent_recovers_from_invalid_structured_tool_call() -> None:
    from typing import Any

    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
    from typing_extensions import override

    from app.agents.api_automation.case_generation.agent import api_automation_generation_agent

    class RecordingFakeModel(FakeMessagesListChatModel):
        requests: list[list[BaseMessage]] = []

        @override
        def bind_tools(self, tools: Any, **kwargs: Any):
            return self

        @override
        def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any):
            self.requests.append(messages)
            return super()._generate(messages, *args, **kwargs)

    tool_call_id = "call-invalid-json"
    model = RecordingFakeModel(
        responses=[
            AIMessage(
                content="",
                invalid_tool_calls=[
                    {
                        "id": tool_call_id,
                        "name": "ApiAutomationGenerationResult",
                        "args": '{"summary": "broken", "cases": [}',
                        "error": "invalid JSON",
                        "type": "invalid_tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-valid-json",
                        "name": "ApiAutomationGenerationResult",
                        "args": {"summary": "recovered", "cases": []},
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )

    agent = api_automation_generation_agent(model, load_references=False)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": "generate"}]})

    assert result["structured_response"] == ApiAutomationGenerationResult(
        summary="recovered",
        cases=[],
    )
    assert len(model.requests) == 2
    recovery_messages = [message for message in model.requests[1] if isinstance(message, ToolMessage)]
    assert len(recovery_messages) == 1
    assert recovery_messages[0].tool_call_id == tool_call_id
    assert recovery_messages[0].status == "error"


def test_api_automation_generation_result_schema_uses_typed_assertions() -> None:
    schema = ApiAutomationGenerationResult.model_json_schema()

    assertion_schema = schema["$defs"]["ApiAssertion"]
    assert "jsonpath_type" in assertion_schema["properties"]["type"]["enum"]
    assert assertion_schema["properties"]["expected"]["anyOf"] == [
        {"type": "string"},
        {"type": "integer"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
    ]
    assert schema["$defs"]["ApiGeneratedCase"]["properties"]["assertions"]["items"] == {
        "$ref": "#/$defs/ApiAssertion"
    }


def test_generated_case_rejects_unsupported_jsonpath_type() -> None:
    with pytest.raises(ValueError, match="标准 JSON 类型"):
        ApiGeneratedCase(
            title="响应类型错误",
            endpoint_id="apiend-1",
            test_point_key="success.minimum_valid",
            oracle_status="confirmed",
            request={"method": "POST", "path": "/analysis"},
            assertions=[{"type": "jsonpath_type", "path": "$.code", "expected": "integer"}],
        )


def test_generated_case_unwraps_minimax_text_encoded_request_and_test_data() -> None:
    case = ApiGeneratedCase(
        title="登录成功",
        endpoint_id="apiend-1",
        test_point_key="success.minimum_valid",
        oracle_status="confirmed",
        request={
            "$text": '{"method":"POST","path":"/login","query":{},"headers":{},"body":{"username":"demo"}}'
        },
        test_data={"$text": '{"account":"demo"}'},
        assertions=[{"type": "status_code", "expected": 200}],
    )

    assert case.request.model_dump(exclude_unset=True) == {
        "method": "POST",
        "path": "/login",
        "query": {},
        "headers": {},
        "body": {"username": "demo"},
    }
    assert case.test_data == {"account": "demo"}


def test_generated_case_rejects_invalid_text_encoded_request() -> None:
    with pytest.raises(ValueError, match=r"request\.\$text.*有效 JSON 对象"):
        ApiGeneratedCase(
            title="登录成功",
            endpoint_id="apiend-1",
            test_point_key="success.minimum_valid",
            oracle_status="confirmed",
            request={"$text": "not-json"},
            assertions=[{"type": "status_code", "expected": 200}],
        )


def test_generated_case_rejects_text_encoded_request_without_method_or_path() -> None:
    with pytest.raises(ValueError, match="method"):
        ApiGeneratedCase(
            title="登录成功",
            endpoint_id="apiend-1",
            test_point_key="success.minimum_valid",
            oracle_status="confirmed",
            request={"$text": '{"path":"/login"}'},
            assertions=[{"type": "status_code", "expected": 200}],
        )


@pytest.mark.anyio
async def test_generate_api_test_cases_calls_agent_with_skill_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.api_automation.case_generation import service as agent_service

    expected = ApiAutomationGenerationResult(
        summary="生成 1 条接口自动化用例。",
        cases=[
            ApiGeneratedCase(
                title="登录成功",
                priority="P1",
                endpoint_id="apiend-1",
                test_point_key="success.minimum_valid",
                oracle_status="confirmed",
                request={"method": "POST", "path": "/login", "body": {"username": "demo", "password": "demo"}},
                assertions=[{"type": "status_code", "expected": 200}],
            )
        ],
    )
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["content"] = payload["messages"][0]["content"]
            return {"structured_response": expected}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["selection"] = selection
        captured["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        agent_service,
        "resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-chat"),
    )
    monkeypatch.setattr(agent_service, "build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(agent_service, "api_automation_generation_agent", lambda model: FakeAgent())

    result = await agent_service.generate_api_test_cases(
        agent_service.ApiAutomationGenerationInput(
            project_id="project-1",
            endpoints=[
                {
                    "id": "apiend-1",
                    "method": "POST",
                    "path": "/login",
                    "summary": "登录",
                    "parameters": [],
                    "request_body": {"content": {"application/json": {"schema": {"type": "object"}}}},
                    "responses": {"200": {"description": "ok"}},
                }
            ],
            generation_goal="覆盖登录正向用例",
            include_security_cases=False,
        )
    )

    assert result is expected
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "请依据系统提示中的 api-automation-case-generation 规则生成接口自动化用例" in captured["content"]
    assert "覆盖登录正向用例" in captured["content"]
    assert "apiend-1" in captured["content"]
    assert "通用覆盖要求" not in captured["content"]
    assert "required path/query/header/body" not in captured["content"]
    assert "不要强行套用某个 4xx" not in captured["content"]


def test_api_automation_case_generation_skill_defines_coverage_dimensions() -> None:
    skill_text = Path(
        "app/agents/api_automation/case_generation/skills/api-automation-case-generation/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "测试点全集" in skill_text
    assert "强制工作流" in skill_text
    assert "组合与去重" in skill_text
    assert "覆盖类型" in skill_text
    for test_point in [
        "字段存在性和可空性",
        "类型、格式和约束",
        "字符与序列化",
        "日期、时间和字段关系",
        "鉴权与安全",
        "查询语义",
        "业务规则、数据影响和重复操作",
        "请求和响应契约",
        "上传接口",
        "下载接口",
    ]:
        assert test_point in skill_text

    assert "不设固定数量" in skill_text
    assert "优先级只用于排序，不得用于截断测试点" in skill_text
    assert "不生成 `scenario`" in skill_text
    assert '"files"' in skill_text
    assert "body_not_empty" in skill_text
    assert "缺少明确状态码、业务错误码或错误消息时，不得跳过用例" in skill_text
    assert "正确 Mock 数据" in skill_text
    assert "错误 Mock 数据" in skill_text
    assert "generation_notes" in skill_text
    assert "用例仍然可以直接执行" in skill_text
