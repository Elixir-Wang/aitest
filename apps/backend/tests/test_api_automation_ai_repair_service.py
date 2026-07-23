from pathlib import Path

import yaml

import pytest

from app.core import db as db_core
from app.core import settings
from app.core import storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import self_healing
from app.agents.api_automation.self_healing.schemas import FailureDiagnosis, FailureIssue, RepairProposal


ADMIN = {"id": "u-admin", "role": "admin", "username": "admin", "nickname": "管理员"}


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", tmp_path / "projects")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()
    suite = settings.PROJECT_FILE_STORAGE_ROOT / "project-1" / "api_automation" / "pytest_requests"
    suite.mkdir(parents=True)
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "项目一", "u-admin"),
        )
        api_automation_repo.create_api_run(
            db,
            run_id="apirun-1",
            task_id="api_automation_run:apirun-1",
            project_id="project-1",
            api_environment_id=None,
            script_ids=["script-1"],
            command_summary="pytest",
            created_by="u-admin",
            status="failed",
        )
    return suite


def test_create_repair_session_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)

    first = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)
    second = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)

    assert first["session_id"] == second["session_id"]
    assert first["attempt_id"] == second["attempt_id"]
    assert first["status"] == "queued"

    with connect() as db:
        attempts = api_automation_repo.list_repair_attempts(db, first["session_id"])
    assert len(attempts) == 1


def test_diagnosis_stage_does_not_generate_candidate_patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    created = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)
    repair_called = False

    async def fake_diagnose_failure(**_kwargs):
        return FailureDiagnosis(
            summary="接口参数校验可能未生效",
            issues=[
                FailureIssue(
                    failure_ids=["failure-1"],
                    classification="interface_bug",
                    confidence=0.9,
                    root_cause="接口未拒绝非法参数",
                    recommendation="检查接口参数校验",
                    repairable=False,
                )
            ],
        )

    async def fake_repair_failure(**_kwargs):
        nonlocal repair_called
        repair_called = True

    monkeypatch.setattr(self_healing, "resolve_model_selection", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(self_healing, "build_agent_model", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(self_healing, "thinking_disabled_extra_body", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(self_healing, "diagnose_failure", fake_diagnose_failure)
    monkeypatch.setattr(self_healing, "repair_failure", fake_repair_failure)

    self_healing.execute_repair_attempt(created["attempt_id"])

    with connect() as db:
        attempt = api_automation_repo.find_repair_attempt(db, created["attempt_id"])
    attempt_dir = self_healing._attempt_dir("project-1", created["session_id"], 1)
    serialized = self_healing._serialize_attempt(attempt)
    assert attempt["status"] == "proposal_ready"
    assert not (attempt_dir / "workspace").exists()
    assert repair_called is False
    assert serialized["available_actions"] == ["reanalyze"]


def test_create_next_repair_attempt_uses_current_session_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup(monkeypatch, tmp_path)
    created = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)
    with connect() as db:
        api_automation_repo.update_repair_attempt(db, created["attempt_id"], status="proposal_ready")

    next_attempt = self_healing.create_next_repair_attempt(
        "project-1", created["session_id"], "补充诊断信息", ADMIN
    )

    with connect() as db:
        attempts = api_automation_repo.list_repair_attempts(db, created["session_id"])
    assert next_attempt["status"] == "queued"
    assert len(attempts) == 2
    assert attempts[-1]["attempt_number"] == 2
    assert attempts[-1]["base_run_id"] == "apirun-1"
    assert attempts[-1]["base_revision"] == 0
    assert attempts[-1]["user_context"] == "补充诊断信息"


def test_create_next_repair_attempt_rejects_active_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _setup(monkeypatch, tmp_path)
    created = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)

    with pytest.raises(Exception) as exc_info:
        self_healing.create_next_repair_attempt("project-1", created["session_id"], "", ADMIN)

    assert getattr(exc_info.value, "detail", {}).get("code") == "API_REPAIR_ATTEMPT_NOT_REANALYZABLE"


def test_approve_proposal_does_not_apply_formal_suite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    suite = _setup(monkeypatch, tmp_path)
    sentinel = suite / "test_endpoint.py"
    sentinel.write_text("ORIGINAL = True\n", encoding="utf-8")
    created = self_healing.create_repair_session("project-1", "apirun-1", "", ADMIN)
    diagnosis = FailureDiagnosis(
        summary="测试断言实现错误",
        issues=[
            FailureIssue(
                failure_ids=["failure-1"],
                classification="test_code_issue",
                confidence=0.95,
                root_cause="测试代码错误",
                recommendation="修改断言实现",
                repairable=True,
            )
        ],
        proposal=RepairProposal(
            target="test_script",
            action="modify_assertion",
            title="修复状态码断言实现",
            summary="仅修改测试公共断言代码。",
            confidence=0.95,
            proposed_changes=["修改 utils/assertions.py"],
            script_repair_allowed=True,
        ),
    )
    with connect() as db:
        api_automation_repo.update_repair_attempt(
            db,
            created["attempt_id"],
            status="waiting_approval",
            diagnosis=diagnosis.model_dump(),
        )

    result = self_healing.approve_repair_attempt("project-1", created["attempt_id"], "批准", ADMIN)

    assert result["status"] == "candidate_generating"
    assert result["applied_run_id"] is None
    assert sentinel.read_text(encoding="utf-8") == "ORIGINAL = True\n"


def test_case_updates_write_database_and_ai_repair_version(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "cases.yaml").write_text(
        yaml.safe_dump(
            [
                {
                    "case_id": "orphaned-case",
                    "assertions": [{"type": "status_code", "path": "", "expected": 400}],
                },
                {
                    "case_id": "case-1",
                    "assertions": [{"type": "status_code", "path": "", "expected": 200}],
                    "oracle_status": "confirmed",
                    "notes": "经实际响应校准",
                }
            ],
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with connect() as db:
        db.execute(
            "INSERT INTO api_test_cases (id, project_id, title, priority, coverage, source, preconditions_json, request_json, test_data_json, expected_json, assertions_json, variables_json, data_origin_json, data_file_path, notes, created_by, test_description, test_point_key, oracle_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "case-1", "project-1", "示例", "P1", "negative", "ai_generated", "[]", "{}", "{}", "{}", "[]", "{}", "{}", "", "", "u-admin", "", "", "needs_confirmation",
            ),
        )
        self_healing._load_case_updates(
            workspace,
            "project-1",
            db,
            case_ids={"case-1"},
            created_by="u-admin",
        )
        row = api_automation_repo.find_api_test_case(db, "case-1")
        versions = api_automation_repo.list_api_test_case_versions(db, "case-1")

    assert api_automation_repo.loads_json(row["assertions_json"], [])[0]["expected"] == 200
    assert row["oracle_status"] == "confirmed"
    assert row["notes"] == "经实际响应校准"
    assert len(versions) == 1
    assert versions[0]["change_source"] == "ai_repair"


def test_apply_proposed_case_updates_calibrates_status_and_confirms_oracle(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_path = workspace / "cases.yaml"
    data_path.write_text(
        yaml.safe_dump(
            [
                {
                    "case_id": "case-1",
                    "oracle_status": "needs_confirmation",
                    "assertions": [{"type": "status_code", "path": "", "expected": 400}],
                    "notes": "按常见约定推断为 400。",
                }
            ],
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    updates = self_healing._apply_proposed_case_updates(
        workspace,
        [{"case_id": "case-1", "expected_status_code": 400, "actual_status_code": 200}],
    )
    case = yaml.safe_load(data_path.read_text(encoding="utf-8"))[0]

    assert case["assertions"][0]["expected"] == 200
    assert case["oracle_status"] == "confirmed"
    assert "人工审批后生效" in case["notes"]
    assert updates[0]["changes"]["assertions"][0]["expected"] == 200
