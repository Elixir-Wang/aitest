import asyncio
import json
from pathlib import Path

import pytest

from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    RequirementObligation,
    RequirementObligationExtractionResult,
    TestPointGenerationResult as GenerationResult,
)
from app.core import db as core_db
from app.core import storage
from app.repositories import test_point_repo
from app.seed.init_db import init_db
from app.services import test_point_service


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _seed_run(*, with_existing_point: bool = False) -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-1', 'finalized', ?)
            """,
            ("doc-1", "project-1", "最终需求", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, '', 'requirement_analysis_finalize', '确认最终需求', ?)
            """,
            ("version-1", "doc-1", "# 最终需求\n规则一。\n规则二。", "u-admin"),
        )
        test_point_repo.create_run(
            db,
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            task_id="test_point_generation:run-1",
            input_json="{}",
            created_by="u-admin",
        )
        if with_existing_point:
            test_point_repo.replace_obligations(
                db,
                project_id="project-1",
                document_id="doc-1",
                version_id="version-1",
                obligations=[item.model_dump() for item in _obligations().obligations],
            )
            test_point_repo.replace_points(
                db,
                run_id="run-1",
                project_id="project-1",
                document_id="doc-1",
                version_id="version-1",
                points=[_stored_point("existing", "旧的完整测试点")],
            )
            test_point_repo.replace_point_obligation_links(
                db,
                version_id="version-1",
                links={"tp-existing": ["REQ-001"]},
            )


def _obligations() -> RequirementObligationExtractionResult:
    return RequirementObligationExtractionResult(
        obligations=[
            RequirementObligation(
                obligation_key="REQ-001",
                source_section="规则一",
                statement="规则一",
                obligation_type="business_rule",
            ),
            RequirementObligation(
                obligation_key="REQ-002",
                source_section="规则二",
                statement="规则二",
                obligation_type="business_rule",
            ),
        ]
    )


def _generated_point(key: str, obligation_key: str) -> GeneratedTestPoint:
    return GeneratedTestPoint(
        point_key=key,
        title=key,
        module="模块",
        category="功能",
        priority="P0",
        description="描述",
        verification_points=["操作 → 预期结果"],
        requirement_obligation_keys=[obligation_key],
    )


def _stored_point(key: str, title: str) -> dict:
    return {
        "id": f"tp-{key}",
        "point_key": key,
        "title": title,
        "module": "模块",
        "category": "功能",
        "priority": "P0",
        "description": "描述",
        "preconditions": [],
        "verification_points": ["操作 → 预期结果"],
        "source_refs": ["最终需求"],
        "notes": "",
    }


def test_enqueue_regeneration_clears_existing_points_and_links(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run(with_existing_point=True)
    with core_db.connect() as db:
        test_point_repo.update_run(db, "run-1", status="completed")

    run = test_point_service.enqueue_generation(
        "project-1",
        "doc-1",
        {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
    )

    with core_db.connect() as db:
        points = test_point_repo.list_points(db, "doc-1", "version-1")
        links = test_point_repo.list_point_obligation_links(db, "version-1")

    assert run["status"] == "queued"
    assert points == []
    assert links == {}


def test_atomize_module_obligations_keeps_multi_agent_independently_coverable():
    obligations = test_point_service._atomize_module_obligations(
        [
            RequirementObligation(
                obligation_key="REQ-003",
                source_section="涉及配置项位置",
                statement="支持思考模式的模型显示思考模式开关",
                obligation_type="display",
                modules=[
                    "自主规划Agent - 对话模型配置弹窗",
                    "Multi-Agent - Agent节点 - 对话模型配置弹窗",
                    "写作Agent - 正文生成模型配置弹窗",
                ],
            )
        ]
    )

    assert [item.obligation_key for item in obligations] == [
        "REQ-003.M01",
        "REQ-003.M02",
        "REQ-003.M03",
    ]
    assert [item.modules for item in obligations] == [
        ["自主规划Agent - 对话模型配置弹窗"],
        ["Multi-Agent - Agent节点 - 对话模型配置弹窗"],
        ["写作Agent - 正文生成模型配置弹窗"],
    ]


def test_generation_supplements_only_missing_obligations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()
    calls = []

    async def fake_extract(input_data):
        return _obligations()

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        calls.append(missing_obligation_keys)
        if missing_obligation_keys:
            return GenerationResult(points=[_generated_point("point-2", "REQ-002")])
        return GenerationResult(points=[_generated_point("point-1", "REQ-001")])

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    with core_db.connect() as db:
        run = test_point_repo.find_run(db, "run-1")
        points = test_point_repo.list_points(db, "doc-1", "version-1")
        links = test_point_repo.list_point_obligation_links(db, "version-1")

    assert calls == [None, ["REQ-002"]]
    assert run["status"] == "completed"
    assert run["coverage_status"] == "complete"
    assert run["obligation_count"] == 2
    assert run["covered_obligation_count"] == 2
    assert {point["point_key"] for point in points} == {"point-1", "point-2"}
    assert sorted(key for values in links.values() for key in values) == ["REQ-001", "REQ-002"]


def test_generation_ignores_unverifiable_requirement_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()
    calls = []

    async def fake_extract(input_data):
        return _obligations().model_copy(
            update={"unverifiable_items": ["Go 版本待补充", "超过限制后的处理未定义"]}
        )

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        calls.append(missing_obligation_keys)
        return GenerationResult(
            points=[
                _generated_point("point-1", "REQ-001"),
                _generated_point("point-2", "REQ-002"),
            ]
        )

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    with core_db.connect() as db:
        run = test_point_repo.find_run(db, "run-1")

    assert calls == [None]
    assert run["status"] == "completed"
    assert run["coverage_status"] == "complete"
    assert run["obligation_count"] == 2
    assert run["covered_obligation_count"] == 2
    assert json.loads(run["unsupported_assumptions_json"]) == []


def test_generation_merges_obligation_links_when_supplement_reuses_point_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()

    async def fake_extract(input_data):
        return _obligations()

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        obligation_key = "REQ-002" if missing_obligation_keys else "REQ-001"
        return GenerationResult(points=[_generated_point("shared-point", obligation_key)])

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    with core_db.connect() as db:
        run = test_point_repo.find_run(db, "run-1")
        links = test_point_repo.list_point_obligation_links(db, "version-1")

    assert run["status"] == "completed"
    assert list(links.values()) == [["REQ-001", "REQ-002"]]


def test_generation_stops_after_no_progress_and_preserves_existing_points_and_links(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run(with_existing_point=True)

    async def fake_extract(input_data):
        return _obligations()

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        return GenerationResult(points=[_generated_point("point-1", "REQ-001")])

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    with core_db.connect() as db:
        run = test_point_repo.find_run(db, "run-1")
        points = test_point_repo.list_points(db, "doc-1", "version-1")

    assert run["status"] == "failed"
    assert run["coverage_status"] == "incomplete"
    assert json.loads(run["missing_obligations_json"]) == ["REQ-002"]
    assert run["supplement_round"] == 1
    assert [point["title"] for point in points] == ["旧的完整测试点"]
    with core_db.connect() as db:
        links = test_point_repo.list_point_obligation_links(db, "version-1")
    assert links == {"tp-existing": ["REQ-001"]}


def test_first_incomplete_generation_persists_missing_obligation_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()

    async def fake_extract(input_data):
        return _obligations()

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        return GenerationResult(points=[_generated_point("point-1", "REQ-001")])

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    overview = test_point_service.get_overview(
        "project-1",
        "doc-1",
        {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
    )
    assert overview["coverage_summary"]["missing_obligations"] == [
        {
            "obligation_key": "REQ-002",
            "source_section": "规则二",
            "statement": "规则二",
        }
    ]
    assert overview["coverage_summary"]["covered_obligation_count"] == 1
    assert overview["coverage_summary"]["obligation_count"] == 2


def test_failed_overview_uses_run_coverage_without_duplicate_module_gaps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run(with_existing_point=True)
    with core_db.connect() as db:
        test_point_repo.update_run(
            db,
            "run-1",
            status="failed",
            coverage_status="incomplete",
            obligation_count=2,
            covered_obligation_count=1,
            missing_obligations_json=json.dumps(["REQ-002:模块"], ensure_ascii=False),
            supplement_round=1,
        )

    overview = test_point_service.get_overview(
        "project-1",
        "doc-1",
        {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
    )

    assert overview["coverage_summary"]["covered_obligation_count"] == 1
    assert overview["coverage_summary"]["obligation_count"] == 2
    assert [item["obligation_key"] for item in overview["coverage_summary"]["missing_obligations"]] == ["REQ-002"]


def test_publish_failure_rolls_back_points_obligations_and_links(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run(with_existing_point=True)

    async def fake_extract(input_data):
        return _obligations()

    async def fake_generate(input_data, *, obligations, existing_points=None, missing_obligation_keys=None):
        return GenerationResult(
            points=[
                _generated_point("point-1", "REQ-001"),
                _generated_point("point-2", "REQ-002"),
            ]
        )

    def fail_replace_points(*args, **kwargs):
        raise RuntimeError("publish failed")

    monkeypatch.setattr(test_point_service, "extract_requirement_obligations", fake_extract)
    monkeypatch.setattr(test_point_service, "generate_test_points", fake_generate)
    monkeypatch.setattr(test_point_repo, "replace_points", fail_replace_points)

    asyncio.run(test_point_service.execute_generation_run("run-1"))

    with core_db.connect() as db:
        run = test_point_repo.find_run(db, "run-1")
        points = test_point_repo.list_points(db, "doc-1", "version-1")
        obligations = test_point_repo.list_obligations(db, "doc-1", "version-1")
        links = test_point_repo.list_point_obligation_links(db, "version-1")

    assert run["status"] == "failed"
    assert run["error_message"] == "publish failed"
    assert [point["title"] for point in points] == ["旧的完整测试点"]
    assert [item["obligation_key"] for item in obligations] == ["REQ-001", "REQ-002"]
    assert links == {"tp-existing": ["REQ-001"]}
