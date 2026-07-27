from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents.api_automation.orchestration.schemas import (
    ScenarioPlanEdge,
    ScenarioPlanNode,
    ScenarioPlanResult,
    binding_to_runtime,
)
from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.schemas.api_automation import ApiScenarioAiPlanApplyIn, ApiScenarioAiPlanIn, ApiScenarioIn, ApiScenarioStepIn
from app.seed.init_db import init_db
from app.services.api_automation import service
from app.services.api_automation.orchestration_compiler import compile_plan


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, method: str = "GET") -> str:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    init_db()
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
            method=method,
            path="/profile",
            normalized_path="/profile",
            summary="用户资料",
            description="",
            tags=["user"],
            parameters=[],
            request_body={},
            responses={"200": {"description": "ok"}},
            auth={},
            source={},
            created_by=ACTOR["id"],
        )
    return service.create_api_scenario("project-1", ApiScenarioIn(name="资料场景"), ACTOR)["id"]


def _mock_plan_agent(monkeypatch: pytest.MonkeyPatch, plan: ScenarioPlanResult) -> None:
    class FakeAgent:
        async def ainvoke(self, _payload):
            return {"structured_response": plan}

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability: SimpleNamespace(provider="test", model="fake"),
    )
    monkeypatch.setattr(service, "thinking_disabled_extra_body", lambda _selection: None)
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, extra_body=None: object())
    monkeypatch.setattr(service, "api_scenario_orchestration_agent", lambda _model: FakeAgent())


def _valid_plan(**node_updates) -> ScenarioPlanResult:
    node = ScenarioPlanNode(
        id="step-profile",
        type="api_request",
        endpoint_id="apiend-1",
        name="查询资料",
        assertions=[{"type": "status_code", "expected": 200}],
        **node_updates,
    )
    return ScenarioPlanResult(scenario_name="查询资料", nodes=[node], confidence=0.9)


def test_ai_plan_is_preview_until_explicitly_applied(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)
    _mock_plan_agent(monkeypatch, _valid_plan())

    plan = service.create_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
        ACTOR,
    )
    assert plan["validation"]["valid"] is True
    recovered = service.get_api_scenario_ai_plan("project-1", plan["plan_id"], ACTOR)
    assert recovered["plan_id"] == plan["plan_id"]
    assert recovered["status"] == "preview"
    assert service.get_api_scenario("project-1", scenario_id, ACTOR)["steps"] == []

    applied = service.apply_api_scenario_ai_plan(
        "project-1",
        plan["plan_id"],
        ApiScenarioAiPlanApplyIn(
            scenario_id=scenario_id,
            expected_revision=plan["expected_revision"],
            confirmation="apply_preview",
        ),
        ACTOR,
    )
    assert [step["endpoint_id"] for step in applied["steps"]] == ["apiend-1"]
    with connect() as db:
        row = db.execute("SELECT status FROM api_scenario_ai_plans WHERE id = ?", (plan["plan_id"],)).fetchone()
        assert row["status"] == "applied"


@pytest.mark.parametrize(
    ("method", "node_updates", "expected_error"),
    [
        ("POST", {}, "禁止写操作"),
        ("GET", {"request_overrides": {"url": "https://outside.example"}}, "不允许携带 AI 生成的 URL"),
    ],
)
def test_ai_plan_rejects_unsafe_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    method: str,
    node_updates: dict,
    expected_error: str,
) -> None:
    scenario_id = _setup(monkeypatch, tmp_path, method=method)
    _mock_plan_agent(monkeypatch, _valid_plan(**node_updates))

    plan = service.create_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
        ACTOR,
    )

    assert plan["validation"]["valid"] is False
    assert any(expected_error in error for error in plan["validation"]["errors"])


def test_ai_plan_rejects_cycles() -> None:
    plan = ScenarioPlanResult(
        nodes=[
            ScenarioPlanNode(id="a", type="api_request", endpoint_id="apiend-1"),
            ScenarioPlanNode(id="b", type="api_request", endpoint_id="apiend-1"),
        ],
        edges=[ScenarioPlanEdge(source="a", target="b"), ScenarioPlanEdge(source="b", target="a")],
    )
    validation = service._validate_ai_plan(
        "project-1",
        plan,
        [{"id": "apiend-1", "method": "GET", "project_id": "project-1"}],
        False,
    )
    assert validation["valid"] is False
    assert "AI 计划不能包含循环依赖。" in validation["errors"]


def test_compiler_binds_json_response_to_required_multipart_field() -> None:
    endpoints = [
        {
            "id": "generate-code",
            "method": "POST",
            "path": "/segment-code/gen",
            "summary": "生成分段码",
            "parameters": [],
            "request_body": {},
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": {"data": {"type": "object", "properties": {"segment_code": {"type": "string"}}}}}
                        }
                    }
                }
            },
        },
        {
            "id": "stream-segment",
            "method": "POST",
            "path": "/segment/stream",
            "summary": "流式处理分段",
            "parameters": [],
            "request_body": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["segment_code"],
                            "properties": {"segment_code": {"type": "string"}},
                        }
                    }
                },
            },
            "responses": {"200": {"description": "ok"}},
        },
    ]
    compiled = compile_plan(
        ScenarioPlanResult(
            scenario_name="生成并处理",
            nodes=[
                ScenarioPlanNode(id="generate", type="api_request", endpoint_id="generate-code"),
                ScenarioPlanNode(id="stream", type="api_request", endpoint_id="stream-segment"),
            ],
        ),
        endpoints,
        {"configured": False, "variables": [], "secrets": [], "auth_type": "none"},
    )

    generate, stream = compiled.nodes
    assert generate.extractors[0].name == "segment_code"
    assert generate.extractors[0].path == "/data/segment_code"
    assert stream.bindings[0].target.location == "multipart"
    assert stream.bindings[0].target.path == "/segment_code"
    assert stream.bindings[0].source.type == "step_output"
    assert stream.bindings[0].source.step_id == "generate"
    assert binding_to_runtime(stream.bindings[0])["target"] == "/request/multipart_form/segment_code"
    assert [(edge.source, edge.target) for edge in compiled.edges] == [("generate", "stream")]


def test_legacy_pointer_binding_remains_accepted() -> None:
    step = ApiScenarioStepIn(
        endpoint_id="apiend-1",
        bindings=[
            {
                "target": "/request/multipart_form/segment_code",
                "source": {"type": "step_output", "step_id": "generate", "variable": "segment_code"},
            }
        ],
    )

    assert step.bindings[0].target.location == "multipart"
    assert step.bindings[0].target.path == "/segment_code"


def test_ai_plan_rejects_forward_step_output_reference() -> None:
    plan = ScenarioPlanResult(
        nodes=[
            ScenarioPlanNode(
                id="consumer",
                type="api_request",
                endpoint_id="apiend-1",
                bindings=[
                    {
                        "target": {"location": "query", "path": "/segment_code"},
                        "source": {"type": "step_output", "step_id": "producer", "variable": "segment_code"},
                    }
                ],
            ),
            ScenarioPlanNode(
                id="producer",
                type="api_request",
                endpoint_id="apiend-1",
                extractors=[{"name": "segment_code", "path": "$.data.segment_code"}],
            ),
        ]
    )

    validation = service._validate_ai_plan(
        "project-1",
        plan,
        [{"id": "apiend-1", "method": "GET", "project_id": "project-1"}],
        False,
    )

    assert validation["valid"] is False
    assert "节点 consumer 的变量来源 引用了后续步骤输出：producer.segment_code。" in validation["errors"]
