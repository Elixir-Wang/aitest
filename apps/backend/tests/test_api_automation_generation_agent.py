from pathlib import Path

import pytest

from app.agents.model_selection import ModelSelection
from app.agents.api_automation.schemas import ApiAutomationGenerationResult, ApiGeneratedCase
from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiAutomationGenerateIn
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


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


def test_execute_generation_run_saves_ready_and_needs_input_cases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()

    async def fake_generate_api_test_cases(input_data):
        return ApiAutomationGenerationResult(
            summary="生成 2 条",
            cases=[
                ApiGeneratedCase(
                    title="登录成功",
                    priority="P1",
                    endpoint_id="apiend-1",
                    preconditions=["用户账号存在"],
                    request={"method": "POST", "path": "/login", "body": {"username": "demo", "password": "demo"}},
                    test_data={
                        "username": {"value": "demo", "source": "openapi_example", "required": True},
                        "password": {"value": "demo", "source": "openapi_example", "required": True},
                    },
                    expected={"status_code": 200},
                    assertions=[{"type": "status_code", "expected": 200}],
                    data_origin={"request.body": "openapi_example", "assertions": "openapi"},
                    status="ready",
                ),
                ApiGeneratedCase(
                    title="登录缺少密码",
                    priority="P2",
                    endpoint_id="apiend-1",
                    coverage="negative",
                    preconditions=["用户账号存在", "缺少 password 测试数据"],
                    request={"method": "POST", "path": "/login", "body": {"username": "demo"}},
                    test_data={
                        "password": {
                            "value": "${password}",
                            "source": "needs_input",
                            "required": True,
                            "status": "missing",
                            "note": "缺少密码样例",
                        }
                    },
                    expected={"status_code": 400},
                    assertions=[{"type": "status_code", "expected": 400}],
                    data_origin={"test_data.password": "needs_input"},
                    status="needs_input",
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
    assert len(cases) == 2
    assert {case["status"] for case in cases} == {"ready", "needs_input"}
    serialized_cases = service.list_api_test_cases("project-1", ACTOR)
    ready_case = next(case for case in serialized_cases if case["status"] == "ready")
    needs_input_case = next(case for case in serialized_cases if case["status"] == "needs_input")
    assert ready_case["coverage"] == "positive"
    assert ready_case["preconditions"] == ["用户账号存在"]
    assert ready_case["test_data"]["username"]["source"] == "openapi_example"
    assert ready_case["data_origin"]["assertions"] == "openapi"
    assert needs_input_case["coverage"] == "negative"
    assert needs_input_case["preconditions"] == ["用户账号存在", "缺少 password 测试数据"]
    assert needs_input_case["test_data"]["password"]["status"] == "missing"
    assert needs_input_case["data_origin"]["test_data.password"] == "needs_input"
    assert api_automation_repo.loads_json(run["result_summary_json"], {})["needs_input_count"] == 1


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
            status="ready",
            tags=[],
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
            status="ready",
            tags=["auth"],
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
    assert detail["data_origin"]["test_data.username"] == "openapi_example"


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


def test_api_automation_agent_uses_skill_middleware_and_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.api_automation import agent as agent_module

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
    assert "api-automation-case-generation" in str(captured["middleware"][0].skill_path)
    assert captured["response_format"] is ApiAutomationGenerationResult


def test_api_automation_generation_result_schema_uses_typed_assertions() -> None:
    schema = ApiAutomationGenerationResult.model_json_schema()

    assertion_schema = schema["$defs"]["ApiAssertion"]
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


@pytest.mark.anyio
async def test_generate_api_test_cases_calls_agent_with_skill_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.api_automation import service as agent_service

    expected = ApiAutomationGenerationResult(
        summary="生成 1 条接口自动化用例。",
        cases=[
            ApiGeneratedCase(
                title="登录成功",
                priority="P1",
                endpoint_id="apiend-1",
                request={"method": "POST", "path": "/login", "body": {"username": "demo", "password": "demo"}},
                expected={"status_code": 200},
                assertions=[{"type": "status_code", "expected": 200}],
                status="ready",
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
    assert "请使用 api-automation-case-generation skill 生成接口自动化用例" in captured["content"]
    assert "覆盖登录正向用例" in captured["content"]
    assert "apiend-1" in captured["content"]
    assert "通用覆盖要求" not in captured["content"]
    assert "required path/query/header/body" not in captured["content"]
    assert "不要强行套用某个 4xx" not in captured["content"]


def test_api_automation_case_generation_skill_defines_coverage_dimensions() -> None:
    skill_text = Path("app/agents/api_automation/skills/api-automation-case-generation/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "覆盖维度模型" in skill_text
    assert "适用性判断" in skill_text
    assert "取舍算法" in skill_text
    assert "Coverage 映射" in skill_text
    for dimension in [
        "happy_path",
        "contract",
        "input_validation",
        "auth_access",
        "business_rule",
        "error_handling",
        "query_semantics",
        "data_effect",
        "integration_mode",
        "scenario_flow",
    ]:
        assert dimension in skill_text

    assert "required 字段缺失只是 `input_validation` 的一种等价类" in skill_text
    assert "不要把所有接口机械套同一批场景" in skill_text
    assert "同一维度下使用等价类压缩" in skill_text
