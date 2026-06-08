from pathlib import Path
import asyncio

import pytest

from app.core import db as core_db
from app.core import storage
from app.api.v1 import exploration as exploration_api
from app.schemas.exploration import ExplorationRunCreateIn
from app.seed.init_db import init_db
from app.services.exploration import service as exploration_service
from app.services.exploration import artifact_service
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


def _confirm_plan(run_id: str) -> None:
    _write_discovery_artifacts(run_id, ["首页"])
    exploration_service.generate_project_run_plan("project-1", run_id, ACTOR)
    exploration_service.confirm_project_run_plan("project-1", run_id, ACTOR)


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
            max_actions=20,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    _confirm_plan(created["id"])
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
    assert (artifact_root / "exploration-plan.yaml").exists()
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


def test_generate_confirmed_plan_before_starting_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="工作台探索",
            scope="工作台",
            forbidden_paths="删除\n发布",
            goal="工作台模块的全部内容",
            notes="",
            max_pages=10,
            max_actions=20,
            timeout_minutes=5,
        ),
        ACTOR,
    )

    first_discovery = exploration_service.start_project_run("project-1", created["id"], ACTOR)
    assert first_discovery["status"] == "queued"
    _write_discovery_artifacts(created["id"], ["工作台"])

    generated = exploration_service.generate_project_run_plan("project-1", created["id"], ACTOR)

    assert generated["plan_status"] == "draft"
    assert generated["business_boundary"] == "工作台"
    assert {item["capability_type"] for item in generated["items"]} == {"module_discovery"}

    confirmed = exploration_service.confirm_project_run_plan("project-1", created["id"], ACTOR)

    assert confirmed["plan_status"] == "confirmed"
    started = exploration_service.start_project_run("project-1", created["id"], ACTOR)
    assert started["status"] == "queued"


def test_generate_plan_uses_first_discovery_modules_instead_of_built_in_capabilities(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="工作台探索",
            scope="工作台",
            forbidden_paths="",
            goal="采集探索范围全部模块",
            notes="",
            max_pages=10,
            max_actions=20,
            timeout_minutes=5,
        ),
        ACTOR,
    )
    _write_discovery_artifacts(created["id"], ["工作台", "资源库", "效果评测"])

    generated = exploration_service.generate_project_run_plan("project-1", created["id"], ACTOR)

    assert generated["plan_status"] == "draft"
    assert generated["summary"] == "已根据首次探索采集结果生成 3 个模块计划项，等待人工确认或补充。"
    assert [item["business_module"] for item in generated["items"]] == ["工作台", "资源库", "效果评测"]
    assert {item["capability_type"] for item in generated["items"]} == {"module_discovery"}
    assert not {"search", "filter", "sort", "create", "import"} & {
        item["capability_type"] for item in generated["items"]
    }


def test_generate_plan_requires_first_discovery_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    created = exploration_service.create_project_run(
        "project-1",
        ExplorationRunCreateIn(
            environment_id="env-1",
            title="工作台探索",
            scope="工作台",
            forbidden_paths="",
            goal="采集探索范围全部模块",
            notes="",
            max_pages=10,
            max_actions=20,
            timeout_minutes=5,
        ),
        ACTOR,
    )

    with pytest.raises(Exception) as missing_artifact_error:
        exploration_service.generate_project_run_plan("project-1", created["id"], ACTOR)

    assert "请先执行首次探索，采集探索范围内的模块。" in str(missing_artifact_error.value)


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
    _confirm_plan(created["id"])
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
