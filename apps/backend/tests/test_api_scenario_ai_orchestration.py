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


def test_ai_plan_failure_is_persisted_for_task_center(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)

    class FailingAgent:
        async def ainvoke(self, _payload):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        service,
        "resolve_model_selection",
        lambda _capability: SimpleNamespace(provider="test", model="fake"),
    )
    monkeypatch.setattr(service, "thinking_disabled_extra_body", lambda _selection: None)
    monkeypatch.setattr(service, "build_agent_model", lambda _selection, extra_body=None: object())
    monkeypatch.setattr(service, "api_scenario_orchestration_agent", lambda _model: FailingAgent())

    with pytest.raises(Exception, match="model unavailable"):
        service.create_api_scenario_ai_plan(
            "project-1",
            ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
            ACTOR,
        )

    with connect() as db:
        row = db.execute(
            "SELECT lifecycle_status, error_message FROM api_scenario_ai_plans ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    assert row["lifecycle_status"] == "failed"
    assert row["error_message"] == "model unavailable"


def test_ai_plan_request_has_no_generation_limits() -> None:
    constraint_fields = ApiScenarioAiPlanIn.model_fields["constraints"].annotation.model_fields

    assert "max_steps" not in constraint_fields
    assert "allow_write" not in constraint_fields


@pytest.mark.parametrize("source_type", ["user_input", "secret", "generated"])
def test_runtime_supported_variable_sources_are_accepted(source_type: str) -> None:
    errors: list[str] = []
    source = {
        "type": source_type,
        "name" if source_type == "user_input" else "key" if source_type == "secret" else "generator":
        "value" if source_type == "generated" else "credential",
    }

    service._validate_scenario_source(source, {}, set(), "步骤 1（生成 SegmentCode）", errors)

    assert errors == []


def test_validation_messages_are_deduplicated() -> None:
    messages = ["重复错误", "重复错误", "另一个错误", "重复错误"]

    assert service._dedupe_validation_messages(messages) == ["重复错误", "另一个错误"]


def test_ai_plan_allows_write_requests(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path, method="POST")
    _mock_plan_agent(monkeypatch, _valid_plan())

    plan = service.create_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="更新用户资料", scenario_id=scenario_id),
        ACTOR,
    )

    assert plan["validation"]["valid"] is True


def test_ai_plan_rejects_generated_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)
    _mock_plan_agent(monkeypatch, _valid_plan(request_overrides={"url": "https://outside.example"}))

    plan = service.create_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
        ACTOR,
    )

    assert plan["validation"]["valid"] is False
    assert any("不允许携带 AI 生成的 URL" in error for error in plan["validation"]["errors"])


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


def test_compiler_normalizes_form_binding_and_deduplicates_multipart_targets() -> None:
    endpoint = {
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
    }
    plan = ScenarioPlanResult(
        nodes=[
            ScenarioPlanNode(
                id="stream",
                type="api_request",
                endpoint_id="stream-segment",
                bindings=[
                    {
                        "target": {"location": "form", "path": "/segment_code"},
                        "source": {"type": "step_output", "step_id": "generate", "variable": "segment_code"},
                    },
                    {
                        "target": {"location": "multipart", "path": "/segment_code"},
                        "source": {"type": "step_output", "step_id": "generate", "variable": "segment_code"},
                    },
                ],
            )
        ]
    )

    compiled = compile_plan(plan, [endpoint], {"configured": False, "variables": [], "secrets": [], "auth_type": "none"})

    assert len(compiled.nodes[0].bindings) == 1
    assert compiled.nodes[0].bindings[0].target.location == "multipart"


def test_compiler_calibrates_existing_extractor_to_asset_response_slot() -> None:
    endpoint = {
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
                        "schema": {
                            "type": "object",
                            "properties": {
                                "data": {
                                    "type": "object",
                                    "properties": {"segment_code": {"type": "string"}},
                                }
                            },
                        }
                    }
                }
            }
        },
    }

    compiled = compile_plan(
        ScenarioPlanResult(
            nodes=[
                ScenarioPlanNode(
                    id="generate",
                    type="api_request",
                    endpoint_id="generate-code",
                    extractors=[{"name": "segment_code", "path": "/segment_code"}],
                )
            ]
        ),
        [endpoint],
        {"configured": False, "variables": [], "secrets": [], "auth_type": "none"},
    )

    assert compiled.nodes[0].extractors[0].path == "/data/segment_code"


def test_multi_agent_segment_sse_plan_has_no_structural_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)
    with connect() as db:
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-generate-segment",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/openapi/v1/gw/multi-agent/segment-code/gen",
            normalized_path="/openapi/v1/gw/multi-agent/segment-code/gen",
            summary="生成 SegmentCode",
            description="",
            tags=[],
            parameters=[
                {"name": "cybertron-robot-key", "in": "header", "required": True, "schema": {"type": "string"}},
                {"name": "cybertron-robot-token", "in": "header", "required": True, "schema": {"type": "string"}},
                {"name": "cybertron-app-id", "in": "header", "required": True, "schema": {"type": "string"}},
            ],
            request_body={
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["message_source"],
                            "properties": {"message_source": {"type": "string"}},
                        }
                    }
                },
            },
            responses={
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "object",
                                        "properties": {"segment_code": {"type": "string"}},
                                    }
                                },
                            }
                        }
                    }
                }
            },
            auth={},
            source={},
            created_by=ACTOR["id"],
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-multi-agent-sse",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/openapi/v1/gw/multi-agent/sse",
            normalized_path="/openapi/v1/gw/multi-agent/sse",
            summary="Multi-Agent SSE 对话",
            description="",
            tags=[],
            parameters=[
                {"name": "cybertron-robot-key", "in": "header", "required": True, "schema": {"type": "string"}},
                {"name": "cybertron-robot-token", "in": "header", "required": True, "schema": {"type": "string"}},
                {"name": "cybertron-app-id", "in": "header", "required": True, "schema": {"type": "string"}},
                {"name": "SSE-Backend-Type", "in": "header", "required": True, "schema": {"type": "string"}},
            ],
            request_body={
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["segment_code", "message_source", "username", "data"],
                            "properties": {
                                "segment_code": {"type": "string"},
                                "message_source": {"type": "string"},
                                "username": {"type": "string"},
                                "data": {"type": "string"},
                            },
                        }
                    }
                },
            },
            responses={"200": {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
            auth={},
            source={},
            created_by=ACTOR["id"],
        )

    plan = ScenarioPlanResult(
        scenario_name="Multi-Agent 生成 SegmentCode 并发起 SSE 对话",
        nodes=[
            ScenarioPlanNode(
                id="gen_segment_code",
                type="api_request",
                endpoint_id="apiend-generate-segment",
                bindings=[
                    {"target": {"location": "header", "path": "/cybertron-robot-key"}, "source": {"type": "secret", "key": "cybertron_robot_key"}},
                    {"target": {"location": "header", "path": "/cybertron-robot-token"}, "source": {"type": "secret", "key": "cybertron_robot_token"}},
                    {"target": {"location": "header", "path": "/cybertron-app-id"}, "source": {"type": "literal", "value": "multi-agent-server"}},
                    {"target": {"location": "form", "path": "/message_source"}, "source": {"type": "user_input", "name": "message_source"}},
                ],
                extractors=[{"name": "segment_code", "path": "/segment_code"}],
            ),
            ScenarioPlanNode(
                id="multi_agent_sse",
                type="api_request",
                endpoint_id="apiend-multi-agent-sse",
                bindings=[
                    {"target": {"location": "header", "path": "/cybertron-robot-key"}, "source": {"type": "secret", "key": "cybertron_robot_key"}},
                    {"target": {"location": "header", "path": "/cybertron-robot-token"}, "source": {"type": "secret", "key": "cybertron_robot_token"}},
                    {"target": {"location": "header", "path": "/cybertron-app-id"}, "source": {"type": "literal", "value": "multi-agent-server"}},
                    {"target": {"location": "header", "path": "/SSE-Backend-Type"}, "source": {"type": "literal", "value": "sse"}},
                    {"target": {"location": "form", "path": "/segment_code"}, "source": {"type": "step_output", "step_id": "gen_segment_code", "variable": "segment_code"}},
                    {"target": {"location": "form", "path": "/message_source"}, "source": {"type": "user_input", "name": "message_source"}},
                    {"target": {"location": "form", "path": "/username"}, "source": {"type": "user_input", "name": "username"}},
                    {"target": {"location": "form", "path": "/data"}, "source": {"type": "user_input", "name": "data"}},
                ],
            ),
        ],
        edges=[{"source": "gen_segment_code", "target": "multi_agent_sse"}],
        confidence=0.76,
    )
    _mock_plan_agent(monkeypatch, plan)

    result = service.create_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="编排 SegmentCode 生成和 SSE 对话", scenario_id=scenario_id),
        ACTOR,
    )

    assert result["validation"]["valid"] is True
    assert result["validation"]["errors"] == []
    assert result["nodes"][0]["extractors"][0]["path"] == "/data/segment_code"
    assert len(result["nodes"][1]["bindings"]) == 8
    assert len({(binding["target"]["location"], binding["target"]["path"]) for binding in result["nodes"][1]["bindings"]}) == 8


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
    )

    assert validation["valid"] is False
    assert "节点 consumer 的变量来源 引用了后续步骤输出：producer.segment_code。" in validation["errors"]


def test_enqueue_ai_plan_returns_generating_handle_before_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)

    accepted = service.enqueue_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
        ACTOR,
    )

    assert accepted["plan_id"].startswith("aiplan-")
    assert accepted["scenario_id"] == scenario_id
    assert accepted["lifecycle_status"] == "generating"
    with connect() as db:
        row = db.execute(
            "SELECT lifecycle_status FROM api_scenario_ai_plans WHERE id = ?",
            (accepted["plan_id"],),
        ).fetchone()
    assert row["lifecycle_status"] == "generating"


def test_get_ai_plan_returns_generating_handle_before_completion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)
    accepted = service.enqueue_api_scenario_ai_plan(
        "project-1",
        ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id),
        ACTOR,
    )

    recovered = service.get_api_scenario_ai_plan("project-1", accepted["plan_id"], ACTOR)

    assert recovered == {
        "plan_id": accepted["plan_id"],
        "scenario_id": accepted["scenario_id"],
        "lifecycle_status": "generating",
    }


def test_enqueue_ai_plan_marks_reused_generating_task_as_not_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    scenario_id = _setup(monkeypatch, tmp_path)
    payload = ApiScenarioAiPlanIn(goal="查询用户资料", scenario_id=scenario_id)

    first = service.enqueue_api_scenario_ai_plan("project-1", payload, ACTOR)
    second = service.enqueue_api_scenario_ai_plan("project-1", payload, ACTOR)

    assert first["created"] is True
    assert second["created"] is False
    assert second["plan_id"] == first["plan_id"]


