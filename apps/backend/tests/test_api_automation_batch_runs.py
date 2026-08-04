import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.schemas.api_automation import ApiScenarioSuiteCreateIn, ApiScenarioSuiteUpdateIn
from app.seed.init_db import init_db
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}


def _configure_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    db_path = data_dir / "ai_testing.db"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", db_path)
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", db_path)
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    return db_path


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    init_db()


def test_init_db_upgrades_legacy_api_runs_before_creating_batch_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = _configure_temp_db(monkeypatch, tmp_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE api_automation_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              api_environment_id TEXT,
              task_id TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'passed', 'observed', 'failed', 'cancelled', 'interrupted')),
              script_ids_json TEXT NOT NULL DEFAULT '[]',
              target_type TEXT NOT NULL DEFAULT 'scripts',
              target_ids_json TEXT NOT NULL DEFAULT '[]',
              execution_snapshot_json TEXT NOT NULL DEFAULT '{}',
              command_summary TEXT NOT NULL DEFAULT '',
              stdout_path TEXT NOT NULL DEFAULT '',
              stderr_path TEXT NOT NULL DEFAULT '',
              json_report_path TEXT NOT NULL DEFAULT '',
              scenario_result_path TEXT NOT NULL DEFAULT '',
              observation_result_path TEXT NOT NULL DEFAULT '',
              parent_run_id TEXT,
              source_repair_attempt_id TEXT,
              summary_json TEXT NOT NULL DEFAULT '{}',
              error_message TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT
            );
            """
        )

    init_db()

    with connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(api_automation_runs)")}
        index = db.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_api_runs_batch_position'"
        ).fetchone()

    assert {"batch_run_id", "batch_position"} <= columns
    assert index is not None


def _seed_project_and_environment() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO api_test_environments (
              id, project_id, name, api_base_url, auth_type, created_by
            ) VALUES (?, ?, ?, ?, 'none', ?)
            """,
            ("apienv-1", "project-1", "测试环境", "https://api.example.test", "u-admin"),
        )


def _seed_ready_scenarios() -> None:
    with connect() as db:
        for scenario_id, name in (("apiscn-1", "登录"), ("apiscn-2", "下单")):
            snapshot = {
                "id": scenario_id,
                "project_id": "project-1",
                "name": name,
                "description": "",
                "variables": {},
                "revision": 1,
                "steps": [{"id": f"apistep-{scenario_id}", "step_type": "control", "enabled": True}],
            }
            serialized_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            db.execute(
                """
                INSERT INTO api_scenarios (
                  id, project_id, name, revision, published_snapshot_json,
                  published_hash, created_by
                ) VALUES (?, 'project-1', ?, 1, ?, ?, 'u-admin')
                """,
                (
                    scenario_id,
                    name,
                    serialized_snapshot,
                    hashlib.sha256(serialized_snapshot.encode("utf-8")).hexdigest(),
                ),
            )
            db.execute(
                """
                INSERT INTO api_scenario_steps (
                  id, scenario_id, project_id, step_type, step_order, name, enabled
                ) VALUES (?, ?, 'project-1', 'control', 0, ?, 1)
                """,
                (f"apistep-{scenario_id}", scenario_id, f"{name}步骤"),
            )


def test_batch_run_persists_ordered_child_run_links(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()

    with connect() as db:
        api_automation_repo.create_api_batch_run(
            db,
            batch_run_id="apibatch-1",
            project_id="project-1",
            api_environment_id="apienv-1",
            name="接口回归批次",
            created_by="u-admin",
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-1",
            task_id="api_automation_run:apirun-1",
            project_id="project-1",
            api_environment_id="apienv-1",
            script_ids=[],
            target_type="scenario",
            target_ids=["apiscn-1"],
            execution_snapshot={"scenario": {"id": "apiscn-1", "name": "登录"}},
            command_summary="python -m pytest scenario_1.py --json-report",
            created_by="u-admin",
            batch_run_id="apibatch-1",
            batch_position=0,
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-2",
            task_id="api_automation_run:apirun-2",
            project_id="project-1",
            api_environment_id="apienv-1",
            script_ids=[],
            target_type="scenario",
            target_ids=["apiscn-2"],
            execution_snapshot={"scenario": {"id": "apiscn-2", "name": "下单"}},
            command_summary="python -m pytest scenario_2.py --json-report",
            created_by="u-admin",
            batch_run_id="apibatch-1",
            batch_position=1,
        )

        batch = api_automation_repo.find_api_batch_run(db, "apibatch-1")
        child_runs = api_automation_repo.list_batch_api_runs(db, "apibatch-1")

    assert batch is not None
    assert batch["status"] == "queued"
    assert [run["id"] for run in child_runs] == ["apirun-1", "apirun-2"]
    assert [run["batch_position"] for run in child_runs] == [0, 1]


def test_create_suite_uses_one_environment_and_preserves_unique_scenario_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    _seed_ready_scenarios()

    suite = service.create_api_scenario_suite(
        "project-1",
        ApiScenarioSuiteCreateIn(
            name="核心接口冒烟",
            description="核心链路",
            api_environment_id="apienv-1",
            scenario_ids=["apiscn-2", "apiscn-1"],
        ),
        ACTOR,
    )

    assert suite["name"] == "核心接口冒烟"
    assert suite["environment"]["id"] == "apienv-1"
    assert [scenario["id"] for scenario in suite["scenarios"]] == ["apiscn-2", "apiscn-1"]

    with pytest.raises(ValueError, match="不能重复选择同一场景"):
        ApiScenarioSuiteCreateIn(
            name="重复场景",
            api_environment_id="apienv-1",
            scenario_ids=["apiscn-1", "apiscn-1"],
        )


def test_suite_can_be_updated_and_deleted_without_deleting_historical_batch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    _seed_ready_scenarios()

    suite = service.create_api_scenario_suite(
        "project-1",
        ApiScenarioSuiteCreateIn(
            name="核心接口冒烟",
            api_environment_id="apienv-1",
            scenario_ids=["apiscn-1"],
        ),
        ACTOR,
    )
    updated = service.update_api_scenario_suite(
        "project-1",
        suite["id"],
        ApiScenarioSuiteUpdateIn(
            name="核心接口回归",
            description="更新后的测试集",
            api_environment_id="apienv-1",
            scenario_ids=["apiscn-2", "apiscn-1"],
        ),
        ACTOR,
    )
    with connect() as db:
        api_automation_repo.create_api_batch_run(
            db,
            batch_run_id="apibatch-history",
            suite_id=suite["id"],
            project_id="project-1",
            api_environment_id="apienv-1",
            name=updated["name"],
            created_by="u-admin",
        )

    service.delete_api_scenario_suite("project-1", suite["id"], ACTOR)

    with connect() as db:
        assert api_automation_repo.find_api_scenario_suite(db, suite["id"]) is None
        historical_batch = api_automation_repo.find_api_batch_run(db, "apibatch-history")

    assert historical_batch is not None
    assert historical_batch["suite_id"] is None
    assert historical_batch["name"] == "核心接口回归"


def test_running_same_suite_twice_creates_two_batches_and_preserves_scenario_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    _seed_ready_scenarios()
    created_calls: list[tuple[str, str]] = []

    def fake_create_scenario_run(project_id: str, scenario_id: str, environment_id: str, actor) -> dict:
        created_calls.append((scenario_id, environment_id))
        run_id = f"apirun-{len(created_calls)}"
        with connect() as db:
            api_automation_repo.create_api_run(
                db,
                run_id=run_id,
                task_id=f"api_automation_run:{run_id}",
                project_id=project_id,
                api_environment_id=environment_id,
                script_ids=[],
                target_type="scenario",
                target_ids=[scenario_id],
                execution_snapshot={"scenario": {"id": scenario_id, "name": scenario_id}},
                command_summary="python -m pytest scenario.py --json-report",
                created_by=actor["id"],
            )
        return {"id": run_id}

    monkeypatch.setattr(service, "create_api_scenario_run", fake_create_scenario_run)

    suite = service.create_api_scenario_suite(
        "project-1",
        ApiScenarioSuiteCreateIn(
            name="核心接口冒烟",
            api_environment_id="apienv-1",
            scenario_ids=["apiscn-2", "apiscn-1"],
        ),
        ACTOR,
    )
    first_batch = service.run_api_scenario_suite("project-1", suite["id"], ACTOR)
    second_batch = service.run_api_scenario_suite("project-1", suite["id"], ACTOR)

    assert created_calls == [
        ("apiscn-2", "apienv-1"),
        ("apiscn-1", "apienv-1"),
        ("apiscn-2", "apienv-1"),
        ("apiscn-1", "apienv-1"),
    ]
    assert first_batch["id"] != second_batch["id"]
    assert first_batch["suite_id"] == suite["id"]
    assert second_batch["suite_id"] == suite["id"]
    assert [run["batch_position"] for run in first_batch["runs"]] == [0, 1]
    assert [run["batch_position"] for run in second_batch["runs"]] == [0, 1]


def test_execute_batch_runs_children_serially_and_aggregates_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_and_environment()
    execution_order: list[str] = []

    with connect() as db:
        api_automation_repo.create_api_batch_run(
            db,
            batch_run_id="apibatch-1",
            project_id="project-1",
            api_environment_id="apienv-1",
            name="接口批量运行",
            created_by="u-admin",
        )
        for position, run_id in enumerate(("apirun-1", "apirun-2")):
            api_automation_repo.create_api_run(
                db,
                run_id=run_id,
                task_id=f"api_automation_run:{run_id}",
                project_id="project-1",
                api_environment_id="apienv-1",
                script_ids=[],
                target_type="scenario",
                target_ids=[f"apiscn-{position + 1}"],
                execution_snapshot={"scenario": {"id": f"apiscn-{position + 1}", "name": run_id}},
                command_summary="python -m pytest scenario.py --json-report",
                created_by="u-admin",
                batch_run_id="apibatch-1",
                batch_position=position,
            )

    def fake_execute_api_run(run_id: str) -> dict:
        execution_order.append(run_id)
        status = "passed" if run_id == "apirun-1" else "failed"
        with connect() as db:
            api_automation_repo.update_api_run(db, run_id, status=status, summary={"total": 1}, finished=True)
        return {"id": run_id, "status": status}

    monkeypatch.setattr(service, "execute_api_run", fake_execute_api_run)

    batch = service.execute_api_batch_run("apibatch-1")

    assert execution_order == ["apirun-1", "apirun-2"]
    assert batch["status"] == "completed"
    assert batch["result"] == "failed"
    assert batch["counts"] == {"total": 2, "passed": 1, "observed": 0, "failed": 1, "error": 0}
