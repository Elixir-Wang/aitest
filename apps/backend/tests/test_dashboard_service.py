import pytest

from app.core import db as core_db
from app.seed.init_db import init_db
from app.services import dashboard_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _seed_project(db, project_id: str, name: str) -> None:
    db.execute(
        "INSERT INTO projects (id, name, status, description) VALUES (?, ?, 'active', '')",
        (project_id, name),
    )
    db.execute(
        """
        INSERT INTO source_documents (id, project_id, name, document_type, status, created_by)
        VALUES (?, ?, ?, 'PRD', 'pending_merge', 'u-admin')
        """,
        (f"doc-{project_id}", project_id, f"{name}需求"),
    )
    db.execute(
        """
        INSERT INTO test_case_sets
          (id, project_id, name, requirement_doc_id, generation_scope_type, status, case_count, created_by)
        VALUES (?, ?, ?, ?, 'all', 'ready_for_review', 0, 'u-admin')
        """,
        (f"set-{project_id}", project_id, f"{name}用例集", f"doc-{project_id}"),
    )


def _seed_case(db, project_id: str, case_id: str, status: str, created_at: str = "2026-07-08 10:00:00") -> None:
    db.execute(
        """
        INSERT INTO test_cases
          (id, test_case_set_id, project_id, title, module, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, '登录', ?, ?, ?)
        """,
        (case_id, f"set-{project_id}", project_id, f"用例 {case_id}", status, created_at, created_at),
    )


def test_dashboard_all_scope_uses_real_test_cases_not_stale_daily_stats(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db, "project-a", "项目A")
        _seed_project(db, "project-b", "项目B")
        _seed_case(db, "project-a", "case-a1", "approved")
        _seed_case(db, "project-a", "case-a2", "ready_for_review")
        _seed_case(db, "project-b", "case-b1", "rejected")
        db.execute(
            """
            INSERT INTO dashboard_daily_stats
              (id, project_id, stat_date, case_assets, adopted_cases, automation_cases, generated_cases)
            VALUES ('stale-a', 'project-a', '2026-07-08', 0, 0, 0, 0)
            """
        )

    overview = dashboard_service.dashboard_overview("all", 7, ACTOR)

    metrics = {metric["label"]: metric for metric in overview["metrics"]}
    assert metrics["项目数"]["value"] == "2"
    assert metrics["用例资产数"]["value"] == "3"
    assert metrics["用例资产数"]["helper"] == "已采纳 1 条"
    assert metrics["测试用例采纳率"]["value"] == "33%"
    assert metrics["自动化用例数量"]["value"] == "0"
    assert metrics["自动化用例数量"]["helper"] == "用例数量 0 条"
    assert overview["trend"][-1]["caseAssets"] == 3
    assert overview["trend"][-1]["adoptedCases"] == 1
    assert overview["trend"][-1]["automationCases"] == 0


def test_dashboard_project_scope_counts_only_selected_project(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_project(db, "project-a", "项目A")
        _seed_project(db, "project-b", "项目B")
        _seed_case(db, "project-a", "case-a1", "approved")
        _seed_case(db, "project-b", "case-b1", "approved")
        _seed_case(db, "project-b", "case-b2", "ready_for_review")

    overview = dashboard_service.dashboard_overview("project-b", 7, ACTOR)

    metrics = {metric["label"]: metric for metric in overview["metrics"]}
    assert overview["scope"] == "project"
    assert overview["project_id"] == "project-b"
    assert overview["project_name"] == "项目B"
    assert metrics["项目数"]["value"] == "1"
    assert metrics["用例资产数"]["value"] == "2"
    assert metrics["测试用例采纳率"]["value"] == "50%"
    assert metrics["自动化用例数量"]["value"] == "0"
