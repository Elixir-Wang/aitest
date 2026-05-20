from __future__ import annotations

import sqlite3

from app.core.db import connect
from app.core.security import hash_secret


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              email TEXT NOT NULL UNIQUE,
              nickname TEXT,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('admin', 'tester', 'guest')),
              status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
              project_scope TEXT NOT NULL DEFAULT '全部项目',
              description TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              expires_at TEXT NOT NULL,
              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS model_providers (
              id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              base_url TEXT NOT NULL,
              api_key_hash TEXT NOT NULL DEFAULT '',
              api_key_mask TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(provider, model, base_url),
              FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              code TEXT NOT NULL DEFAULT '',
              default_site_url TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
              description TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS source_documents (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              document_type TEXT NOT NULL,
              original_file_path TEXT NOT NULL,
              current_version_id TEXT,
              status TEXT NOT NULL DEFAULT 'uploaded',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS source_document_versions (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_no INTEGER NOT NULL,
              markdown_content TEXT NOT NULL DEFAULT '',
              file_path TEXT NOT NULL,
              source_action TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              diff_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              UNIQUE(document_id, version_no)
            );

            CREATE TABLE IF NOT EXISTS source_document_file_mappings (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT NOT NULL,
              source_file_path TEXT NOT NULL,
              markdown_file_path TEXT NOT NULL,
              mapping_status TEXT NOT NULL DEFAULT 'parsing',
              conversion_summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dashboard_daily_stats (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              stat_date TEXT NOT NULL,
              case_assets INTEGER NOT NULL,
              adopted_cases INTEGER NOT NULL,
              automation_cases INTEGER NOT NULL,
              generated_cases INTEGER NOT NULL,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, stat_date)
            );
            """
        )
        _ensure_column(db, "model_providers", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "code", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "default_site_url", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "created_by", "TEXT NOT NULL DEFAULT 'system'")
        _seed_user(db, "u-admin", "admin", "admin@example.com", "平台管理员", "admin", "admin", "enabled", "全部项目", "平台管理员，负责用户、模型和项目权限维护。")
        _sync_seed_password(db, "u-admin", "admin")
        _seed_user(db, "u-tester", "tester", "tester@example.com", "测试工程师", "tester123", "tester", "enabled", "知了平台", "负责具体项目测试资产建设。")
        _seed_user(db, "u-guest", "guest", "guest@example.com", "访客", "guest123", "guest", "enabled", "全部项目", "只读查看系统内容与报告。")
        _seed_project(db, "zhiliao", "知了平台", "active", "核心业务项目，承载需求、探索、知识库和测试资产链路。")
        _seed_project(db, "hawk", "鹰眼平台", "active", "示例项目，用于验证跨项目任务、报告和自动化执行流程。")
        _seed_project(db, "atlas", "Atlas 内测", "archived", "归档项目，保留历史需求和用例资产。")
        _seed_dashboard_stats(db)


def _seed_user(db: sqlite3.Connection, user_id: str, username: str, email: str, nickname: str, password: str, role: str, status: str, project_scope: str, description: str) -> None:
    exists = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, email, nickname, hash_secret(password), role, status, project_scope, description),
    )


def _ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column in columns:
        return
    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _sync_seed_password(db: sqlite3.Connection, user_id: str, password: str) -> None:
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_secret(password), user_id),
    )


def _seed_project(db: sqlite3.Connection, project_id: str, name: str, status: str, description: str) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO projects (id, name, status, description)
        VALUES (?, ?, ?, ?)
        """,
        (project_id, name, status, description),
    )


def _seed_dashboard_stats(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM dashboard_daily_stats LIMIT 1").fetchone()
    if exists:
        return

    dates = [
        "2026-05-03",
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
        "2026-05-07",
        "2026-05-08",
        "2026-05-09",
        "2026-05-10",
        "2026-05-11",
        "2026-05-12",
        "2026-05-13",
        "2026-05-14",
        "2026-05-15",
        "2026-05-16",
        "2026-05-17",
        "2026-05-18",
        "2026-05-19",
    ]
    zhiliao = [
        (188, 142, 58, 166),
        (193, 146, 61, 171),
        (198, 151, 65, 176),
        (207, 159, 69, 185),
        (212, 165, 73, 191),
        (218, 170, 77, 198),
        (225, 176, 81, 205),
        (231, 183, 86, 212),
        (236, 189, 90, 219),
        (242, 195, 94, 226),
        (246, 201, 97, 232),
        (251, 207, 101, 239),
        (257, 214, 104, 247),
        (263, 219, 108, 254),
        (269, 225, 111, 261),
        (274, 229, 114, 267),
        (282, 242, 117, 281),
    ]
    hawk = [
        (98, 72, 30, 84),
        (101, 75, 31, 87),
        (104, 78, 33, 90),
        (108, 82, 35, 95),
        (111, 85, 38, 99),
        (113, 88, 40, 102),
        (117, 91, 42, 106),
        (120, 94, 44, 110),
        (123, 97, 46, 114),
        (126, 100, 48, 118),
        (128, 103, 50, 121),
        (131, 106, 52, 125),
        (134, 109, 54, 129),
        (136, 112, 55, 132),
        (138, 114, 57, 135),
        (140, 117, 58, 138),
        (144, 124, 59, 145),
    ]

    for project_id, values in (("zhiliao", zhiliao), ("hawk", hawk)):
        for stat_date, (case_assets, adopted_cases, automation_cases, generated_cases) in zip(dates, values):
            db.execute(
                """
                INSERT INTO dashboard_daily_stats
                  (id, project_id, stat_date, case_assets, adopted_cases, automation_cases, generated_cases)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ds-{project_id}-{stat_date}",
                    project_id,
                    stat_date,
                    case_assets,
                    adopted_cases,
                    automation_cases,
                    generated_cases,
                ),
            )
