from pathlib import Path
import asyncio
import json

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import storage
from app.api.v1 import exploration as exploration_api
from app.schemas.exploration import ExplorationRunCreateIn, ExplorationRunUpdateIn
from app.seed.init_db import init_db
from app.services.exploration import service as exploration_service
from app.services.exploration import artifact_service
from app.services.exploration import event_bus as exploration_event_bus
from app.services.exploration import site_orchestrator


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(exploration_service, "PROJECT_FILE_STORAGE_ROOT", project_root, raising=False)
    init_db()
    return project_root


def _seed_project_and_environment() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES (?, ?, 'active', '')",
            ("project-1", "测试项目"),
        )
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, login_strategy, created_by)
            VALUES (?, ?, ?, ?, 'skip_login', ?)
            """,
            ("env-1", "project-1", "测试环境", "https://example.test", ACTOR["id"]),
        )


def _seed_requirement_document(document_id: str = "doc-1", project_id: str = "project-1", name: str = "登录需求") -> None:
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'uploaded', ?)
            """,
            (document_id, project_id, name, ACTOR["id"]),
        )


def _mark_run_completed(run_id: str) -> None:
    with core_db.connect() as db:
        db.execute(
            "UPDATE exploration_runs SET artifact_root = ?, status = 'completed' WHERE id = ?",
            (f"project-1/exploration/{run_id}", run_id),
        )


def _write_discovery_artifacts(run_id: str, modules: list[str]) -> None:
    artifact_root = storage.PROJECT_FILE_STORAGE_ROOT / "project-1" / "exploration" / run_id
    page_artifacts = []
    for index, module in enumerate(modules, start=1):
        page_artifacts.append(
            {
                "page": {
                    "id": f"page-{index:03d}",
                    "title": f"{module}首页",
                    "url": f"https://example.test/{index}",
                    "normalized_url": f"https://example.test/{index}",
                    "module": module,
                    "depth": index - 1,
                    "status": "explored",
                    "structure_summary": f"{module}页面已采集。",
                },
                "actions": [{"name": f"打开{module}", "type": "navigation"}],
                "forms": [],
                "tables": [],
                "steps": [{"type": "observe", "title": f"观察{module}", "detail": f"采集{module}页面事实。"}],
            }
        )
    artifact_service.write_exploration_artifacts(
        artifact_root,
        run={
            "id": run_id,
            "project_id": "project-1",
            "project_name": "测试项目",
            "environment_id": "env-1",
            "environment_name": "测试环境",
            "title": "工作台探索",
            "site_url": "https://example.test",
            "scope": "工作台",
            "goal": "采集探索范围全部模块",
            "forbidden_paths": "",
            "login_strategy": "skip_login",
            "started_at": "",
            "status": "completed",
            "summary": "首次探索已采集模块。",
            "max_pages": 10,
            "max_actions": 20,
            "timeout_minutes": 5,
        },
        summary={"status": "completed", "summary": "首次探索已采集模块。", "markdown_content": "# 首次探索\n"},
        page_artifacts=page_artifacts,
        graph={"edges": []},
        blockers=[],
        log_content='{"event":"run_completed","status":"completed"}',
        goal_validation={"status": "passed", "summary": "ok", "stats": {}},
    )
    with core_db.connect() as db:
        db.execute(
            "UPDATE exploration_runs SET artifact_root = ?, status = 'completed' WHERE id = ?",
            (f"project-1/exploration/{run_id}", run_id),
        )


def test_restart_recovers_stale_stopping_run_with_completed_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    artifact_root = project_root / "project-1" / "exploration" / created["id"]
    (artifact_root / "logs").mkdir(parents=True, exist_ok=True)
    (artifact_root / "run.yaml").write_text("artifact_schema_version: 2\n", encoding="utf-8")
    (artifact_root / "logs" / "run.log").write_text(
        '{"event":"run_started"}\n{"event":"run_completed","status":"completed"}\n',
        encoding="utf-8",
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'stopping',
                artifact_root = ?,
                result_summary = '用户已请求停止探索，正在终止浏览器探索进程。'
            WHERE id = ?
            """,
            (f"project-1/exploration/{created['id']}", created["id"]),
        )

    restarted = exploration_service.start_project_run("project-1", created["id"], ACTOR)

    assert restarted["status"] == "queued"
    assert restarted["result_summary"] == "探索任务已提交，等待执行。"
    assert not (artifact_root / "run.yaml").exists()
    assert not (artifact_root / "logs" / "run.log").exists()
    with core_db.connect() as db:
        module_count = db.execute(
            "SELECT COUNT(*) AS count FROM exploration_module_coverages WHERE exploration_run_id = ?",
            (created["id"],),
        ).fetchone()["count"]
    assert module_count == 1


def test_create_run_has_no_execution_mode_columns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()

    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )

    assert "execution_mode" not in created
    assert "interaction_mode" not in created
    assert "agent_turn_count" not in created
    with core_db.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(exploration_runs)").fetchall()}
    assert "execution_mode" not in columns
    assert "interaction_mode" not in columns
    assert "agent_turn_count" not in columns


def test_running_run_detail_returns_plan_steps_before_page_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="工作台探索",
            scope="工作台",
            forbidden_paths="",
            goal="模块一：进入工作台\n1. 点击智能体卡片。",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    artifact_root = project_root / "project-1" / "exploration" / created["id"]
    artifact_root.mkdir(parents=True)
    (artifact_root / "exploration-plan.yaml").write_text(
        """
plan_id: plan-1
modules:
  - 工作台
steps:
  - step_id: step-001
    step_number: 1
    action_type: click
    description: 点击智能体卡片
    target_description: 测试_自主规划智能体
    expected_result: 进入智能体详情
    module_name: 工作台
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'running',
                artifact_root = ?,
                result_summary = '开始执行探索计划，共 1 个步骤。'
            WHERE id = ?
            """,
            (f"project-1/exploration/{created['id']}", created["id"]),
        )
        db.execute(
            """
            UPDATE exploration_module_coverages
            SET completion_status = 'running',
                completion_summary = '开始执行探索计划，共 1 个步骤。'
            WHERE exploration_run_id = ?
            """,
            (created["id"],),
        )

    detail = exploration_service.get_project_run_detail("project-1", created["id"], ACTOR)

    module = detail["modules"][0]
    assert module["module_name"] == "工作台"
    assert module["pages"][0]["id"] == "plan-planned-01"
    assert module["pages"][0]["steps"][0]["title"] == "点击智能体卡片"
    assert module["pages"][0]["steps"][0]["source"] == "exploration_plan"


def test_running_run_detail_recovers_live_progress_without_final_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="工作台探索",
            scope="工作台",
            forbidden_paths="",
            goal="点击智能体卡片",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    artifact_root = project_root / "project-1" / "exploration" / created["id"]
    (artifact_root / "live").mkdir(parents=True)
    (artifact_root / "live" / "progress.json").write_text(
        json.dumps(
            {
                "run_id": created["id"],
                "modules": {
                    "planned-01": {
                        "pages": {
                            "lifecycle": {
                                "id": "lifecycle",
                                "module_key": "planned-01",
                                "title": "当前运行阶段",
                                "status": "running",
                                "recent_event": "正在分析探索目标并生成执行步骤。",
                                "steps": [
                                    {
                                        "id": "planning-started",
                                        "type": "planning",
                                        "title": "生成探索计划",
                                        "detail": "正在分析探索目标并生成执行步骤。",
                                        "status": "running",
                                        "source": "unified_orchestrator",
                                    }
                                ],
                            }
                        }
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'running',
                artifact_root = ?,
                result_summary = '正在智能分析探索目标并生成探索计划。'
            WHERE id = ?
            """,
            (f"project-1/exploration/{created['id']}", created["id"]),
        )
        db.execute(
            """
            UPDATE exploration_module_coverages
            SET completion_status = 'running',
                completion_summary = '正在智能分析探索目标并生成探索计划。'
            WHERE exploration_run_id = ?
            """,
            (created["id"],),
        )

    detail = exploration_service.get_project_run_detail("project-1", created["id"], ACTOR)

    module = detail["modules"][0]
    assert module["module_name"] == "工作台"
    assert module["pages"][0]["id"] == "lifecycle"
    assert module["pages"][0]["title"] == "当前运行阶段"
    assert module["pages"][0]["steps"][0]["title"] == "生成探索计划"
    assert module["pages"][0]["steps"][0]["status"] == "running"


def test_detail_does_not_report_zero_page_module_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()

    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="探索",
            scope="工作台",
            forbidden_paths="",
            goal="验证工作台目标",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'partial',
                result_summary = '目标验证部分完成：未探索到页面。',
                started_at = CURRENT_TIMESTAMP,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (created["id"],),
        )
        db.execute(
            """
            INSERT INTO exploration_module_coverages
              (id, exploration_run_id, module_key, module_name, entry_path, planned_page_count,
               explored_page_count, blocked_page_count, action_count, field_count,
               state_transition_count, completion_status, completion_summary)
            VALUES (?, ?, 'unclassified', '未分组模块', '工作台', 1, 0, 0, 0, 0, 0,
                    'completed', '已覆盖 0/1 个页面，最近页面：无，无阻塞。')
            """,
            (f"expcov-{created['id']}", created["id"]),
        )

    detail = exploration_service.get_project_run_detail("project-1", created["id"], ACTOR)

    module = detail["modules"][0]
    assert module["planned_page_count"] == 1
    assert module["explored_page_count"] == 0
    assert module["completion_status"] == "partial"
    assert module["completion_summary"] == "未探索到页面事实，无法确认探索目标已完成。"


def test_create_and_update_run_can_link_requirement_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    _seed_requirement_document()

    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            requirement_doc_id="doc-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )

    assert created["requirement_doc_id"] == "doc-1"
    assert created["requirement_doc_title"] == "登录需求"

    updated = exploration_service.update_project_run(
        "project-1",
        created["id"],
        ExplorationRunUpdateIn(requirement_doc_id=""),
        ACTOR,
    )

    assert updated["requirement_doc_id"] == ""
    assert updated["requirement_doc_title"] == ""


def test_create_run_rejects_requirement_document_from_other_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES (?, ?, 'active', '')",
            ("project-2", "其他项目"),
        )
    _seed_requirement_document(document_id="doc-2", project_id="project-2", name="其他需求")

    with pytest.raises(HTTPException) as exc_info:
        exploration_service.create_project_run(
            "project-1",
            ExplorationRunCreateIn(
                environment_id="env-1",
                requirement_doc_id="doc-2",
                title="首页探索",
                scope="首页",
                forbidden_paths="",
                goal="",
                notes="",
                max_pages=10,
                max_actions=100,
                timeout_minutes=5,
            ),
            ACTOR,
        )

    assert exc_info.value.detail["code"] == "INVALID_REQUIREMENT_DOCUMENT"


def test_detail_recovers_stale_stopping_run_before_frontend_disables_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    artifact_root = project_root / "project-1" / "exploration" / created["id"]
    (artifact_root / "logs").mkdir(parents=True)
    (artifact_root / "run.yaml").write_text("artifact_schema_version: 2\n", encoding="utf-8")
    (artifact_root / "logs" / "run.log").write_text(
        '{"event":"run_started"}\n{"event":"run_completed","status":"completed"}\n',
        encoding="utf-8",
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'stopping',
                artifact_root = ?,
                result_summary = '用户已请求停止探索，正在终止浏览器探索进程。'
            WHERE id = ?
            """,
            (f"project-1/exploration/{created['id']}", created["id"]),
        )

    detail = exploration_service.get_project_run_detail("project-1", created["id"], ACTOR)

    assert detail["run"]["status"] == "completed"
    assert detail["run"]["result_summary"] == "探索已完成，停止请求发生在任务结束后，状态已自动恢复。"


def test_stop_running_run_returns_cancelled_and_closes_browser_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'running',
                result_summary = 'Agentic Loop 已开始，正在观察页面并决策下一步。'
            WHERE id = ?
            """,
            (created["id"],),
        )
        db.execute(
            """
            UPDATE exploration_module_coverages
            SET completion_status = 'running',
                completion_summary = '探索中'
            WHERE exploration_run_id = ?
            """,
            (created["id"],),
        )

    closed: dict[str, object] = {}

    def fake_close_run_session(run_id: str, *, timeout_seconds: float = 1.0) -> bool:
        closed["run_id"] = run_id
        closed["timeout_seconds"] = timeout_seconds
        return True

    monkeypatch.setattr(exploration_service.exploration_browser_session, "close_run_session", fake_close_run_session)

    stopped = exploration_service.stop_project_run("project-1", created["id"], ACTOR)

    assert stopped["status"] == "cancelled"
    assert stopped["result_summary"] == "用户已停止探索，已保留停止前生成的日志和产物。"
    assert closed == {"run_id": created["id"], "timeout_seconds": 1.0}
    with core_db.connect() as db:
        row = db.execute(
            "SELECT status, finished_at FROM exploration_runs WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert row["status"] == "cancelled"
    assert row["finished_at"]


def test_persist_runner_result_does_not_override_cancelled_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(site_orchestrator, "PROJECT_FILE_STORAGE_ROOT", project_root)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    artifact_root = project_root / "project-1" / "exploration" / created["id"]
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'cancelled',
                result_summary = '用户已停止探索，已保留停止前生成的日志和产物。',
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (created["id"],),
        )

    site_orchestrator._persist_runner_result(
        created["id"],
        artifact_root,
        {
            "status": "blocked",
            "summary": "浏览器会话已关闭。",
            "reason_type": "browser_closed",
            "suggested_action": "无需处理。",
            "log_path": "",
        },
    )

    with core_db.connect() as db:
        row = db.execute(
            "SELECT status, result_summary FROM exploration_runs WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert row["status"] == "cancelled"
    assert row["result_summary"] == "用户已停止探索，已保留停止前生成的日志和产物。"


def test_orchestrator_marks_queued_run_running_before_unified_exploration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = _use_temp_db(monkeypatch, tmp_path)
    monkeypatch.setattr(site_orchestrator, "PROJECT_FILE_STORAGE_ROOT", project_root)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    exploration_service.start_project_run("project-1", created["id"], ACTOR)
    captured: dict[str, str] = {}

    def fake_execute_unified_exploration(run_id: str, artifact_root: Path) -> dict:
        with core_db.connect() as db:
            captured["status_before_unified_exploration"] = db.execute(
                "SELECT status FROM exploration_runs WHERE id = ?",
                (run_id,),
            ).fetchone()["status"]
        return {
            "status": "blocked",
            "summary": "统一探索阻塞。",
            "reason_type": "test_blocked",
            "suggested_action": "测试建议。",
            "log_path": "",
            "log": '{"event":"blocked","type":"test_blocked","reason":"统一探索阻塞。"}\n',
        }

    monkeypatch.setattr(site_orchestrator, "_execute_unified_exploration", fake_execute_unified_exploration)

    site_orchestrator.run_exploration(created["id"])

    assert captured["status_before_unified_exploration"] == "running"
    with core_db.connect() as db:
        row = db.execute(
            "SELECT status, result_summary FROM exploration_runs WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert row["status"] == "blocked"
    assert row["result_summary"] == "统一探索阻塞。"


def test_stream_late_subscription_returns_terminal_run_event(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'partial',
                result_summary = '已探索 1 个页面。',
                started_at = CURRENT_TIMESTAMP,
                finished_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (created["id"],),
        )

    response = exploration_api.stream_project_run("project-1", created["id"], ACTOR)
    body = asyncio.run(_streaming_response_text(response))

    assert "event: run_snapshot" in body
    assert "event: run_failed" in body
    assert f'"run_id":"{created["id"]}"' in body
    assert '"run":{"id":' in body
    assert '"status":"partial"' in body
    assert "已探索 1 个页面。" in body


def test_stream_run_replays_snapshot_before_recent_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="首页探索",
            scope="首页",
            forbidden_paths="",
            goal="采集首页",
            notes="",
            max_pages=10,
            max_actions=100,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    with core_db.connect() as db:
        db.execute(
            """
            UPDATE exploration_runs
            SET status = 'running',
                result_summary = '正在执行探索计划。'
            WHERE id = ?
            """,
            (created["id"],),
        )

    exploration_event_bus.reset_for_tests()
    exploration_event_bus.publish(created["id"], "planning_completed", {"total_steps": 1})
    response = exploration_api.stream_project_run("project-1", created["id"], ACTOR)
    iterator = response.body_iterator

    async def read_first_two_events() -> str:
        parts = []
        try:
            async for chunk in iterator:
                parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
                if sum(part.count("\n\n") for part in parts) >= 2:
                    break
        finally:
            await iterator.aclose()
            exploration_event_bus.reset_for_tests()
        return "".join(parts)

    body = asyncio.run(read_first_two_events())

    assert body.index("event: run_snapshot") < body.index("event: planning_completed")
    assert '"result_summary":"正在执行探索计划。"' in body
    assert '"total_steps":1' in body


async def _streaming_response_text(response) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return "".join(parts)
