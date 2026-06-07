from pathlib import Path
import asyncio

import pytest

from app.core import db as core_db
from app.core import storage
from app.api.v1 import exploration as exploration_api
from app.schemas.exploration import ExplorationRunCreateIn
from app.seed.init_db import init_db
from app.services.exploration import service as exploration_service
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
            max_actions=20,
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

    restarted = exploration_service.start_project_run("project-1", created["id"], ACTOR)

    assert restarted["status"] == "queued"
    assert restarted["result_summary"] == "探索任务已提交，等待执行。"
    assert not artifact_root.exists()
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
            max_actions=20,
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
            max_actions=20,
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


def test_orchestrator_marks_queued_run_running_before_agentic_loop(
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
            max_actions=20,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    exploration_service.start_project_run("project-1", created["id"], ACTOR)
    captured: dict[str, str] = {}

    def fake_execute_agentic_loop(run_id: str, artifact_root: Path) -> dict:
        with core_db.connect() as db:
            captured["status_before_agentic_loop"] = db.execute(
                "SELECT status FROM exploration_runs WHERE id = ?",
                (run_id,),
            ).fetchone()["status"]
        return {
            "status": "blocked",
            "summary": "Agentic Loop 阻塞。",
            "reason_type": "test_blocked",
            "suggested_action": "测试建议。",
            "log_path": "",
            "log": '{"event":"blocked","type":"test_blocked","reason":"Agentic Loop 阻塞。"}\n',
        }

    monkeypatch.setattr(site_orchestrator, "_execute_agentic_loop", fake_execute_agentic_loop)

    site_orchestrator.run_exploration(created["id"])

    assert captured["status_before_agentic_loop"] == "running"
    with core_db.connect() as db:
        row = db.execute(
            "SELECT status, result_summary FROM exploration_runs WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert row["status"] == "blocked"
    assert row["result_summary"] == "Agentic Loop 阻塞。"


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
            max_actions=20,
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

    assert "event: run_failed" in body
    assert f'"run_id":"{created["id"]}"' in body
    assert '"status":"partial"' in body
    assert "已探索 1 个页面。" in body


async def _streaming_response_text(response) -> str:
    parts: list[str] = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return "".join(parts)
