import shutil
import sqlite3
from pathlib import Path, PureWindowsPath

from app.core.db import connect
from app.core.environment_auth_state import environment_root
from app.core.environment_scope import GLOBAL_ENVIRONMENT_PROJECT_ID
from app.core.security import hash_secret
from app.core.storage import PROJECT_FILE_STORAGE_ROOT, store_path


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
              api_key TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('enabled', 'disabled')),
              health_status TEXT NOT NULL DEFAULT 'unknown' CHECK(health_status IN ('unknown', 'healthy', 'unhealthy', 'timeout', 'testing')),
              last_test_at TEXT,
              last_test_message TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(provider, model, base_url),
              FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS model_assignments (
              capability_id TEXT PRIMARY KEY,
              model_provider_id TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(model_provider_id) REFERENCES model_providers(id) ON DELETE CASCADE
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
              current_version_id TEXT,
              status TEXT NOT NULL DEFAULT 'collecting',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, name)
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
              version_id TEXT,
              source_file_path TEXT NOT NULL,
              original_filename TEXT NOT NULL DEFAULT '',
              file_format TEXT NOT NULL DEFAULT '',
              markdown_file_path TEXT,
              preview_file_path TEXT,
              conversion_status TEXT NOT NULL DEFAULT 'pending',
              mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
              file_role TEXT NOT NULL DEFAULT 'supporting',
              conversion_summary TEXT NOT NULL DEFAULT '',
              conversion_quality INTEGER,
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS document_version_change_logs (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT NOT NULL,
              source_action TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              diff_summary TEXT NOT NULL DEFAULT '',
              affected_modules TEXT NOT NULL DEFAULT '[]',
              source_mapping_ids TEXT NOT NULL DEFAULT '[]',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS requirement_analyses (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              version_id TEXT,
              primary_mapping_id TEXT,
              status TEXT NOT NULL,
              analysis_summary TEXT NOT NULL DEFAULT '',
              output_json TEXT NOT NULL,
              quality_result TEXT NOT NULL,
              testability_score INTEGER NOT NULL DEFAULT 0,
              draft_content_hash TEXT NOT NULL DEFAULT '',
              finalized_version_id TEXT,
              finalized_at TEXT,
              finalized_by TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL,
              FOREIGN KEY(primary_mapping_id) REFERENCES source_document_file_mappings(id) ON DELETE SET NULL,
              FOREIGN KEY(finalized_version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS requirement_analysis_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              primary_mapping_id TEXT,
              analysis_id TEXT,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'stopping', 'cancelled', 'completed', 'needs_clarification', 'blocked', 'failed')),
              summary TEXT NOT NULL DEFAULT '',
              failure_reason TEXT NOT NULL DEFAULT '',
              previous_current_version_id TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(primary_mapping_id) REFERENCES source_document_file_mappings(id) ON DELETE SET NULL,
              FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS requirement_clarification_answers (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              document_id TEXT NOT NULL,
              analysis_id TEXT NOT NULL,
              question_id TEXT NOT NULL,
              answer_type TEXT NOT NULL CHECK(answer_type IN ('recommended_option', 'custom', 'defer')),
              selected_option_id TEXT NOT NULL DEFAULT '',
              answer_markdown TEXT NOT NULL DEFAULT '',
              user_note TEXT NOT NULL DEFAULT '',
              apply_status TEXT NOT NULL CHECK(apply_status IN ('not_applicable', 'applied', 'failed')),
              insertion_anchor TEXT NOT NULL DEFAULT '',
              failure_reason TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE CASCADE
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

            CREATE TABLE IF NOT EXISTS test_case_sets (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              requirement_doc_id TEXT NOT NULL,
              exploration_run_id TEXT NOT NULL DEFAULT '',
              include_company_knowledge INTEGER NOT NULL DEFAULT 1,
              generation_scope_type TEXT NOT NULL CHECK(generation_scope_type IN ('all', 'specified')),
              generation_scope_text TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('generating', 'ready_for_review', 'failed', 'archived')),
              case_count INTEGER NOT NULL DEFAULT 0,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(requirement_doc_id) REFERENCES source_documents(id) ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_test_case_sets_project_updated
              ON test_case_sets(project_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_test_case_sets_requirement
              ON test_case_sets(requirement_doc_id);

            CREATE TABLE IF NOT EXISTS test_case_generation_runs (
              id TEXT PRIMARY KEY,
              test_case_set_id TEXT NOT NULL,
              task_id TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
              input_json TEXT NOT NULL DEFAULT '{}',
              error_message TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              finished_at TEXT,
              FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_test_case_generation_runs_set
              ON test_case_generation_runs(test_case_set_id, created_at);

            CREATE TABLE IF NOT EXISTS test_cases (
              id TEXT PRIMARY KEY,
              test_case_set_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              title TEXT NOT NULL,
              module TEXT NOT NULL DEFAULT '',
              priority TEXT NOT NULL DEFAULT '',
              preconditions TEXT NOT NULL DEFAULT '',
              steps_json TEXT NOT NULL DEFAULT '[]',
              expected_result TEXT NOT NULL DEFAULT '',
              source_requirement_refs TEXT NOT NULL DEFAULT '[]',
              source_exploration_refs TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL CHECK(status IN ('draft', 'ready_for_review', 'approved', 'rejected')) DEFAULT 'draft',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(test_case_set_id) REFERENCES test_case_sets(id) ON DELETE CASCADE,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS project_environments (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              name TEXT NOT NULL,
              site_url TEXT NOT NULL,
              username TEXT NOT NULL DEFAULT '',
              password_encrypted TEXT NOT NULL DEFAULT '',
              password_hash TEXT NOT NULL DEFAULT '',
              login_strategy TEXT NOT NULL DEFAULT 'skip_login',
              captcha_strategy TEXT NOT NULL DEFAULT 'none',
              reuse_auth_state INTEGER NOT NULL DEFAULT 1,
              description TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS exploration_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              environment_id TEXT NOT NULL,
              requirement_doc_id TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'stopping', 'cancelled', 'interrupted', 'partial', 'completed', 'blocked')) DEFAULT 'pending',
              scope TEXT NOT NULL DEFAULT '',
              forbidden_paths TEXT NOT NULL DEFAULT '',
              login_strategy TEXT NOT NULL DEFAULT 'skip_login',
              goal TEXT NOT NULL DEFAULT '',
              notes TEXT NOT NULL DEFAULT '',
              max_pages INTEGER NOT NULL DEFAULT 50,
              max_actions INTEGER NOT NULL DEFAULT 1000,
              timeout_minutes INTEGER NOT NULL DEFAULT 120,
              artifact_root TEXT NOT NULL DEFAULT '',
              result_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              started_at TEXT,
              finished_at TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS exploration_module_coverages (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL,
              module_name TEXT NOT NULL,
              entry_path TEXT NOT NULL DEFAULT '',
              planned_page_count INTEGER NOT NULL DEFAULT 0,
              explored_page_count INTEGER NOT NULL DEFAULT 0,
              blocked_page_count INTEGER NOT NULL DEFAULT 0,
              action_count INTEGER NOT NULL DEFAULT 0,
              field_count INTEGER NOT NULL DEFAULT 0,
              state_transition_count INTEGER NOT NULL DEFAULT 0,
              completion_status TEXT NOT NULL,
              completion_summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              UNIQUE(exploration_run_id, module_key)
            );

            CREATE TABLE IF NOT EXISTS exploration_pages (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL DEFAULT '',
              url TEXT NOT NULL DEFAULT '',
              entry_path TEXT NOT NULL DEFAULT '',
              structure_summary TEXT NOT NULL DEFAULT '',
              screenshot_path TEXT NOT NULL DEFAULT '',
              snapshot_path TEXT NOT NULL DEFAULT '',
              trace_path TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_elements (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              page_id TEXT,
              module_key TEXT NOT NULL DEFAULT '',
              element_name TEXT NOT NULL,
              element_type TEXT NOT NULL DEFAULT '',
              recommended_locator TEXT NOT NULL DEFAULT '',
              fallback_locator TEXT NOT NULL DEFAULT '',
              stability_note TEXT NOT NULL DEFAULT '',
              source_ref TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              FOREIGN KEY(page_id) REFERENCES exploration_pages(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS exploration_blockers (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              module_key TEXT NOT NULL DEFAULT '',
              page_ref TEXT NOT NULL DEFAULT '',
              reason_type TEXT NOT NULL DEFAULT '',
              reason TEXT NOT NULL,
              evidence_path TEXT NOT NULL DEFAULT '',
              impact_scope TEXT NOT NULL DEFAULT '',
              suggested_action TEXT NOT NULL DEFAULT '',
              is_blocking INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_artifacts (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              artifact_type TEXT NOT NULL,
              file_path TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '',
              summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exploration_document_versions (
              id TEXT PRIMARY KEY,
              exploration_run_id TEXT NOT NULL,
              version_no INTEGER NOT NULL,
              markdown_path TEXT NOT NULL,
              change_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(exploration_run_id) REFERENCES exploration_runs(id) ON DELETE CASCADE,
              UNIQUE(exploration_run_id, version_no)
            );

            CREATE TABLE IF NOT EXISTS operation_logs (
              id TEXT PRIMARY KEY,
              log_type TEXT NOT NULL CHECK(log_type IN ('audit', 'config', 'task', 'agent')),
              module TEXT NOT NULL,
              action TEXT NOT NULL,
              object_type TEXT NOT NULL,
              object_id TEXT,
              object_name TEXT NOT NULL DEFAULT '',
              project_id TEXT,
              actor_id TEXT NOT NULL DEFAULT 'system',
              actor_name TEXT NOT NULL DEFAULT '系统',
              source TEXT NOT NULL CHECK(source IN ('web', 'api', 'agent', 'runner', 'system')),
              result TEXT NOT NULL CHECK(result IN ('success', 'failed', 'partial_success', 'cancelled')),
              failure_reason TEXT NOT NULL DEFAULT '',
              summary TEXT NOT NULL DEFAULT '',
              before_json TEXT NOT NULL DEFAULT '{}',
              after_json TEXT NOT NULL DEFAULT '{}',
              task_id TEXT,
              artifact_path TEXT NOT NULL DEFAULT '[]',
              request_id TEXT NOT NULL DEFAULT '',
              ip_address TEXT NOT NULL DEFAULT '',
              user_agent TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at ON operation_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_project_id_created_at ON operation_logs(project_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_actor_id_created_at ON operation_logs(actor_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_module_action ON operation_logs(module, action);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_object ON operation_logs(object_type, object_id);
            CREATE INDEX IF NOT EXISTS idx_operation_logs_result ON operation_logs(result);

            CREATE TABLE IF NOT EXISTS operation_log_retention_policy (
              id TEXT PRIMARY KEY,
              retention_days INTEGER NOT NULL DEFAULT 180,
              max_rows INTEGER NOT NULL DEFAULT 100000,
              protect_high_risk INTEGER NOT NULL DEFAULT 1,
              updated_by TEXT NOT NULL DEFAULT 'system',
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_documents (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              knowledge_type TEXT NOT NULL,
              scope TEXT NOT NULL DEFAULT '全部项目',
              source_note TEXT NOT NULL DEFAULT '',
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('processing', 'available', 'conversion_failed', 'archived')),
              current_version_id TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              archived_at TEXT,
              UNIQUE(name, knowledge_type)
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_versions (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_no TEXT NOT NULL,
              markdown_content TEXT NOT NULL DEFAULT '',
              markdown_path TEXT NOT NULL DEFAULT '',
              change_summary TEXT NOT NULL DEFAULT '',
              conversion_status TEXT NOT NULL CHECK(conversion_status IN ('queued', 'running', 'success', 'failed')),
              conversion_summary TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES global_knowledge_documents(id) ON DELETE CASCADE,
              UNIQUE(document_id, version_no)
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_files (
              id TEXT PRIMARY KEY,
              version_id TEXT NOT NULL,
              original_filename TEXT NOT NULL,
              file_path TEXT NOT NULL,
              file_type TEXT NOT NULL DEFAULT '',
              file_size INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(version_id) REFERENCES global_knowledge_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_usage_logs (
              id TEXT PRIMARY KEY,
              global_knowledge_version_id TEXT NOT NULL,
              usage_type TEXT NOT NULL,
              target_project_id TEXT,
              target_object_id TEXT NOT NULL DEFAULT '',
              summary TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(global_knowledge_version_id) REFERENCES global_knowledge_versions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_bases (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL CHECK(status IN ('processing', 'available', 'conversion_failed')) DEFAULT 'available',
              root_folder_id TEXT,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS global_knowledge_folders (
              id TEXT PRIMARY KEY,
              knowledge_base_id TEXT NOT NULL,
              parent_id TEXT,
              name TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(knowledge_base_id) REFERENCES global_knowledge_bases(id) ON DELETE CASCADE,
              FOREIGN KEY(parent_id) REFERENCES global_knowledge_folders(id) ON DELETE CASCADE,
              UNIQUE(knowledge_base_id, parent_id, name)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_global_knowledge_root_folder_name
            ON global_knowledge_folders(knowledge_base_id, name)
            WHERE parent_id IS NULL;

            CREATE TABLE IF NOT EXISTS global_knowledge_vault_files (
              id TEXT PRIMARY KEY,
              knowledge_base_id TEXT NOT NULL,
              folder_id TEXT NOT NULL,
              original_filename TEXT NOT NULL,
              display_name TEXT NOT NULL,
              file_type TEXT NOT NULL DEFAULT '',
              file_size INTEGER NOT NULL DEFAULT 0,
              raw_path TEXT NOT NULL DEFAULT '',
              markdown_path TEXT NOT NULL DEFAULT '',
              markdown_content TEXT NOT NULL DEFAULT '',
              conversion_status TEXT NOT NULL CHECK(conversion_status IN ('queued', 'running', 'success', 'failed')) DEFAULT 'success',
              conversion_summary TEXT NOT NULL DEFAULT '',
              sort_order INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(knowledge_base_id) REFERENCES global_knowledge_bases(id) ON DELETE CASCADE,
              FOREIGN KEY(folder_id) REFERENCES global_knowledge_folders(id) ON DELETE CASCADE,
              UNIQUE(folder_id, display_name)
            );

            CREATE TABLE IF NOT EXISTS knowledge_conversations (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '新对话',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
              FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS knowledge_conversation_messages (
              id TEXT PRIMARY KEY,
              conversation_id TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
              content TEXT NOT NULL,
              source_refs_json TEXT NOT NULL DEFAULT '[]',
              used_requirement_versions_json TEXT NOT NULL DEFAULT '[]',
              used_exploration_runs_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(conversation_id) REFERENCES knowledge_conversations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_project_created ON requirement_analysis_runs(project_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_document_created ON requirement_analysis_runs(document_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_status ON requirement_analysis_runs(status);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_requirement_clarification_answers_current ON requirement_clarification_answers(analysis_id, question_id);
            CREATE INDEX IF NOT EXISTS idx_requirement_clarification_answers_document ON requirement_clarification_answers(document_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_documents_status ON global_knowledge_documents(status, updated_at);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_documents_type ON global_knowledge_documents(knowledge_type, updated_at);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_versions_document ON global_knowledge_versions(document_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_bases_updated ON global_knowledge_bases(updated_at);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_folders_base_parent ON global_knowledge_folders(knowledge_base_id, parent_id, sort_order);
            CREATE INDEX IF NOT EXISTS idx_global_knowledge_vault_files_folder ON global_knowledge_vault_files(folder_id, sort_order, display_name);
            CREATE INDEX IF NOT EXISTS idx_knowledge_conversations_project_updated ON knowledge_conversations(project_id, created_by, updated_at);
            CREATE INDEX IF NOT EXISTS idx_knowledge_conversation_messages_conversation_created ON knowledge_conversation_messages(conversation_id, created_at);
            """
        )
        _ensure_column(db, "model_providers", "description", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "model_providers", "api_key", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "model_providers", "health_status", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(db, "model_providers", "last_test_at", "TEXT")
        _ensure_column(db, "model_providers", "last_test_message", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "code", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "default_site_url", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "projects", "created_by", "TEXT NOT NULL DEFAULT 'system'")
        _ensure_column(db, "project_environments", "login_strategy", "TEXT NOT NULL DEFAULT 'skip_login'")
        _ensure_column(db, "project_environments", "captcha_strategy", "TEXT NOT NULL DEFAULT 'none'")
        _ensure_column(db, "project_environments", "reuse_auth_state", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(db, "project_environments", "password_encrypted", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "project_environments", "password_hash", "TEXT NOT NULL DEFAULT ''")
        _drop_column_if_exists(db, "project_environments", "password_mask")
        _ensure_column(db, "exploration_runs", "artifact_root", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "exploration_runs", "result_summary", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "exploration_runs", "started_at", "TEXT")
        _ensure_column(db, "exploration_runs", "finished_at", "TEXT")
        _ensure_column(db, "exploration_runs", "max_pages", "INTEGER NOT NULL DEFAULT 50")
        _ensure_column(db, "exploration_runs", "max_actions", "INTEGER NOT NULL DEFAULT 1000")
        _ensure_column(db, "exploration_runs", "timeout_minutes", "INTEGER NOT NULL DEFAULT 120")
        _ensure_column(db, "exploration_runs", "requirement_doc_id", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(db, "global_knowledge_vault_files", "sort_order", "INTEGER NOT NULL DEFAULT 0")
        _backfill_environment_login_strategies(db)
        _migrate_exploration_run_statuses(db)
        _migrate_source_documents(db)
        _migrate_file_mappings(db)
        _migrate_requirement_analyses(db)
        _migrate_requirement_analysis_run_statuses(db)
        _migrate_agent_model_assignments(db)
        _migrate_knowledge_query_model_assignment(db)
        _migrate_requirement_standardization_model_assignment(db)
        _migrate_remove_retired_model_assignments(db)
        _migrate_stored_paths(db)
        _seed_operation_log_retention_policy(db)
        _ensure_all_projects_conversation_scope(db)
        _ensure_global_environments_project(db)
        _migrate_exploration_environments_to_global(db)
        _seed_user(db, "u-admin", "admin", "admin@example.com", "平台管理员", "admin", "admin", "enabled", "全部项目", "平台管理员，负责用户、模型和项目权限维护。")
        _sync_seed_password(db, "u-admin", "admin")


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


def _drop_column_if_exists(db: sqlite3.Connection, table: str, column: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        return
    db.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


def _ensure_all_projects_conversation_scope(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = '__all_projects__'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO projects (id, name, status, description, created_by)
        VALUES ('__all_projects__', '全部项目知识库', 'archived', '系统保留项目，用于全部项目知识库对话历史。', 'system')
        """
    )


def _ensure_global_environments_project(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM projects WHERE id = '__global_environments__'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO projects (id, name, status, description, created_by)
        VALUES ('__global_environments__', '全局探索环境', 'archived', '系统保留项目，用于存放与业务项目解耦的探索环境。', 'system')
        """
    )


def _migrate_exploration_environments_to_global(db: sqlite3.Connection) -> None:
    used_names = {
        row[0]
        for row in db.execute(
            "SELECT name FROM project_environments WHERE project_id = ?",
            (GLOBAL_ENVIRONMENT_PROJECT_ID,),
        ).fetchall()
    }

    legacy_rows = db.execute(
        "SELECT id, project_id, name FROM project_environments WHERE project_id != ?",
        (GLOBAL_ENVIRONMENT_PROJECT_ID,),
    ).fetchall()
    for row in legacy_rows:
        env_id = row["id"]
        old_project_id = row["project_id"]
        name = row["name"]
        _move_environment_storage(env_id, [PROJECT_FILE_STORAGE_ROOT / old_project_id / "environments" / env_id])

        unique_name = name
        counter = 2
        while unique_name in used_names:
            unique_name = f"{name}-{counter}"
            counter += 1
        used_names.add(unique_name)
        db.execute(
            "UPDATE project_environments SET project_id = ?, name = ? WHERE id = ?",
            (GLOBAL_ENVIRONMENT_PROJECT_ID, unique_name, env_id),
        )

    global_rows = db.execute(
        "SELECT id FROM project_environments WHERE project_id = ?",
        (GLOBAL_ENVIRONMENT_PROJECT_ID,),
    ).fetchall()
    for row in global_rows:
        env_id = row["id"]
        _move_environment_storage(
            env_id,
            [PROJECT_FILE_STORAGE_ROOT / GLOBAL_ENVIRONMENT_PROJECT_ID / "environments" / env_id],
        )


def _move_environment_storage(environment_id: str, legacy_dirs: list[Path]) -> None:
    target_dir = environment_root(environment_id)
    if target_dir.exists():
        return
    for legacy_dir in legacy_dirs:
        if not legacy_dir.exists():
            continue
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_dir), str(target_dir))
        return


def _seed_operation_log_retention_policy(db: sqlite3.Connection) -> None:
    exists = db.execute("SELECT id FROM operation_log_retention_policy WHERE id = 'default'").fetchone()
    if exists:
        return
    db.execute(
        """
        INSERT INTO operation_log_retention_policy (id, retention_days, max_rows, protect_high_risk)
        VALUES ('default', 180, 100000, 1)
        """
    )


def _backfill_environment_login_strategies(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE project_environments
        SET login_strategy = 'skip_login',
            captcha_strategy = 'none',
            reuse_auth_state = 0,
            username = '',
            password_encrypted = '',
            password_hash = ''
        WHERE login_strategy = '' OR login_strategy IS NULL
        """
    )
    db.execute(
        """
        UPDATE project_environments
        SET login_strategy = 'account_password',
            captcha_strategy = CASE
              WHEN login_strategy = 'manual' THEN 'manual'
              ELSE 'none'
            END,
            reuse_auth_state = 1
        WHERE login_strategy IN ('reuse_state', 'manual')
        """
    )


def _migrate_exploration_run_statuses(db: sqlite3.Connection) -> None:
    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'exploration_runs'",
    ).fetchone()
    if not table:
        return
    columns = {row["name"] for row in db.execute("PRAGMA table_info(exploration_runs)").fetchall()}
    required_columns = {"goal", "notes"}
    legacy_columns = {"environment_type", "description", "execution_mode", "interaction_mode", "agent_turn_count"}
    if (
        "'stopping'" in table["sql"]
        and "'interrupted'" in table["sql"]
        and required_columns.issubset(columns)
        and columns.isdisjoint(legacy_columns)
    ):
        return
    source_count = db.execute("SELECT COUNT(*) AS count FROM exploration_runs").fetchone()["count"]
    goal_expr = "goal" if "goal" in columns else ("description" if "description" in columns else "''")
    notes_expr = "notes" if "notes" in columns else "''"
    max_pages_expr = "max_pages" if "max_pages" in columns else "50"
    max_actions_expr = "max_actions" if "max_actions" in columns else "1000"
    timeout_minutes_expr = "timeout_minutes" if "timeout_minutes" in columns else "120"
    artifact_root_expr = "artifact_root" if "artifact_root" in columns else "''"
    result_summary_expr = "result_summary" if "result_summary" in columns else "''"
    started_at_expr = "started_at" if "started_at" in columns else "NULL"
    finished_at_expr = "finished_at" if "finished_at" in columns else "NULL"
    requirement_doc_id_expr = "requirement_doc_id" if "requirement_doc_id" in columns else "''"

    db.execute("PRAGMA foreign_keys=off")
    db.executescript(
        """
        DROP TABLE IF EXISTS exploration_runs_new;
        CREATE TABLE IF NOT EXISTS exploration_runs_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          environment_id TEXT NOT NULL,
          requirement_doc_id TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'stopping', 'cancelled', 'interrupted', 'partial', 'completed', 'blocked')) DEFAULT 'pending',
          scope TEXT NOT NULL DEFAULT '',
          forbidden_paths TEXT NOT NULL DEFAULT '',
          login_strategy TEXT NOT NULL DEFAULT 'skip_login',
          goal TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '',
          max_pages INTEGER NOT NULL DEFAULT 50,
          max_actions INTEGER NOT NULL DEFAULT 1000,
          timeout_minutes INTEGER NOT NULL DEFAULT 120,
          artifact_root TEXT NOT NULL DEFAULT '',
          result_summary TEXT NOT NULL DEFAULT '',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          started_at TEXT,
          finished_at TEXT,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE RESTRICT
        );
        """
    )
    db.execute(
        f"""
        INSERT OR IGNORE INTO exploration_runs_new
          (id, project_id, environment_id, requirement_doc_id, title, status, scope, forbidden_paths, login_strategy, goal, notes,
           max_pages, max_actions, timeout_minutes, artifact_root, result_summary, created_by, created_at, updated_at,
           started_at, finished_at)
        SELECT id, project_id, environment_id, {requirement_doc_id_expr}, title,
               CASE
                 WHEN status = 'queued' AND {started_at_expr} IS NULL THEN 'pending'
                 WHEN status = 'waiting_human' THEN 'partial'
                 ELSE status
               END,
               scope, forbidden_paths, login_strategy, {goal_expr}, {notes_expr},
               {max_pages_expr}, {max_actions_expr}, {timeout_minutes_expr},
               {artifact_root_expr}, {result_summary_expr},
               created_by, created_at, updated_at, {started_at_expr}, {finished_at_expr}
        FROM exploration_runs
        """
    )
    migrated_count = db.execute("SELECT COUNT(*) AS count FROM exploration_runs_new").fetchone()["count"]
    if migrated_count != source_count:
        db.execute("DROP TABLE IF EXISTS exploration_runs_new")
        db.execute("PRAGMA foreign_keys=on")
        raise RuntimeError(f"探索任务迁移行数不一致：原表 {source_count} 行，新表 {migrated_count} 行。")

    db.executescript(
        """
        DROP TABLE exploration_runs;
        ALTER TABLE exploration_runs_new RENAME TO exploration_runs;
        """
    )
    db.execute("PRAGMA foreign_keys=on")


def _migrate_source_documents(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(source_documents)").fetchall()}
    if "original_file_path" not in columns:
        return
    db.executescript(
        """
        PRAGMA foreign_keys=off;
        CREATE TABLE IF NOT EXISTS source_documents_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          name TEXT NOT NULL,
          document_type TEXT NOT NULL,
          current_version_id TEXT,
          status TEXT NOT NULL DEFAULT 'collecting',
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          UNIQUE(project_id, name)
        );
        INSERT OR IGNORE INTO source_documents_new
          (id, project_id, name, document_type, current_version_id, status, created_by, created_at, updated_at)
        SELECT id, project_id, name, document_type, current_version_id, status, created_by, created_at, updated_at
        FROM source_documents;
        DROP TABLE source_documents;
        ALTER TABLE source_documents_new RENAME TO source_documents;
        PRAGMA foreign_keys=on;
        """
    )


def _migrate_file_mappings(db: sqlite3.Connection) -> None:
    columns = {row["name"]: row for row in db.execute("PRAGMA table_info(source_document_file_mappings)").fetchall()}
    version_id_column = columns.get("version_id")
    if (version_id_column and version_id_column["notnull"]) or "conversion_status" not in columns:
        db.executescript(
            """
            PRAGMA foreign_keys=off;
            CREATE TABLE IF NOT EXISTS source_document_file_mappings_new (
              id TEXT PRIMARY KEY,
              document_id TEXT NOT NULL,
              version_id TEXT,
              source_file_path TEXT NOT NULL,
              original_filename TEXT NOT NULL DEFAULT '',
              file_format TEXT NOT NULL DEFAULT '',
              markdown_file_path TEXT,
              preview_file_path TEXT,
              conversion_status TEXT NOT NULL DEFAULT 'success',
              mapping_status TEXT NOT NULL DEFAULT 'pending_merge',
              file_role TEXT NOT NULL DEFAULT 'supporting',
              conversion_summary TEXT NOT NULL DEFAULT '',
              conversion_quality INTEGER,
              created_by TEXT NOT NULL DEFAULT 'system',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
              FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
            );
            INSERT OR IGNORE INTO source_document_file_mappings_new
              (id, document_id, version_id, source_file_path, original_filename, file_format, markdown_file_path,
               conversion_status, mapping_status, file_role, conversion_summary, created_by, created_at)
            SELECT id, document_id, version_id, source_file_path, source_file_path, 'unknown', markdown_file_path,
                   'success', mapping_status, 'supporting', conversion_summary, 'system', created_at
            FROM source_document_file_mappings;
            DROP TABLE source_document_file_mappings;
            ALTER TABLE source_document_file_mappings_new RENAME TO source_document_file_mappings;
            PRAGMA foreign_keys=on;
            """
        )
        return

    _ensure_column(db, "source_document_file_mappings", "original_filename", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "source_document_file_mappings", "file_format", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(db, "source_document_file_mappings", "preview_file_path", "TEXT")
    _ensure_column(db, "source_document_file_mappings", "conversion_status", "TEXT NOT NULL DEFAULT 'success'")
    _ensure_column(db, "source_document_file_mappings", "file_role", "TEXT NOT NULL DEFAULT 'supporting'")
    _ensure_column(db, "source_document_file_mappings", "conversion_quality", "INTEGER")
    _ensure_column(db, "source_document_file_mappings", "created_by", "TEXT NOT NULL DEFAULT 'system'")
    db.execute(
        """
        UPDATE source_document_file_mappings
        SET original_filename = CASE WHEN original_filename = '' THEN source_file_path ELSE original_filename END,
            file_format = CASE WHEN file_format = '' THEN 'unknown' ELSE file_format END
        """
    )


def _migrate_requirement_analysis_run_statuses(db: sqlite3.Connection) -> None:
    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'requirement_analysis_runs'",
    ).fetchone()
    if not table:
        return
    columns = {row["name"] for row in db.execute("PRAGMA table_info(requirement_analysis_runs)").fetchall()}
    if "'stopping'" in table["sql"] and "previous_current_version_id" in columns:
        return

    source_count = db.execute("SELECT COUNT(*) AS count FROM requirement_analysis_runs").fetchone()["count"]
    previous_version_expr = (
        "previous_current_version_id" if "previous_current_version_id" in columns else "NULL"
    )

    db.execute("PRAGMA foreign_keys=off")
    db.executescript(
        f"""
        DROP TABLE IF EXISTS requirement_analysis_runs_new;
        CREATE TABLE IF NOT EXISTS requirement_analysis_runs_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          document_id TEXT NOT NULL,
          primary_mapping_id TEXT,
          analysis_id TEXT,
          status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'stopping', 'cancelled', 'completed', 'needs_clarification', 'blocked', 'failed')),
          summary TEXT NOT NULL DEFAULT '',
          failure_reason TEXT NOT NULL DEFAULT '',
          previous_current_version_id TEXT,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
          FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
          FOREIGN KEY(primary_mapping_id) REFERENCES source_document_file_mappings(id) ON DELETE SET NULL,
          FOREIGN KEY(analysis_id) REFERENCES requirement_analyses(id) ON DELETE SET NULL
        );
        INSERT INTO requirement_analysis_runs_new
          (id, project_id, document_id, primary_mapping_id, analysis_id, status, summary, failure_reason,
           previous_current_version_id, created_by, created_at, updated_at)
        SELECT
          id, project_id, document_id, primary_mapping_id, analysis_id, status, summary, failure_reason,
          {previous_version_expr}, created_by, created_at, updated_at
        FROM requirement_analysis_runs;
        """
    )
    migrated_count = db.execute("SELECT COUNT(*) AS count FROM requirement_analysis_runs_new").fetchone()["count"]
    if migrated_count != source_count:
        db.execute("DROP TABLE IF EXISTS requirement_analysis_runs_new")
        db.execute("PRAGMA foreign_keys=on")
        return
    db.executescript(
        """
        DROP TABLE requirement_analysis_runs;
        ALTER TABLE requirement_analysis_runs_new RENAME TO requirement_analysis_runs;
        """
    )
    db.execute("PRAGMA foreign_keys=on")


def _migrate_requirement_analyses(db: sqlite3.Connection) -> None:
    table = db.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'requirement_analyses'",
    ).fetchone()
    if not table:
        return

    columns = {row["name"]: row for row in db.execute("PRAGMA table_info(requirement_analyses)").fetchall()}
    expected_columns = {
        "primary_mapping_id",
        "draft_content_hash",
        "finalized_version_id",
        "finalized_at",
        "finalized_by",
    }
    version_id_column = columns.get("version_id")
    if version_id_column and not version_id_column["notnull"] and expected_columns.issubset(columns):
        return

    source_count = db.execute("SELECT COUNT(*) AS count FROM requirement_analyses").fetchone()["count"]
    primary_mapping_expr = "primary_mapping_id" if "primary_mapping_id" in columns else "NULL"
    draft_hash_expr = "draft_content_hash" if "draft_content_hash" in columns else "''"
    finalized_version_expr = "finalized_version_id" if "finalized_version_id" in columns else "NULL"
    finalized_at_expr = "finalized_at" if "finalized_at" in columns else "NULL"
    finalized_by_expr = "finalized_by" if "finalized_by" in columns else "NULL"

    db.execute("PRAGMA foreign_keys=off")
    db.executescript(
        """
        DROP TABLE IF EXISTS requirement_analyses_new;
        CREATE TABLE IF NOT EXISTS requirement_analyses_new (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          document_id TEXT NOT NULL,
          version_id TEXT,
          primary_mapping_id TEXT,
          status TEXT NOT NULL,
          analysis_summary TEXT NOT NULL DEFAULT '',
          output_json TEXT NOT NULL,
          quality_result TEXT NOT NULL,
          testability_score INTEGER NOT NULL DEFAULT 0,
          draft_content_hash TEXT NOT NULL DEFAULT '',
          finalized_version_id TEXT,
          finalized_at TEXT,
          finalized_by TEXT,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
          FOREIGN KEY(version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL,
          FOREIGN KEY(primary_mapping_id) REFERENCES source_document_file_mappings(id) ON DELETE SET NULL,
          FOREIGN KEY(finalized_version_id) REFERENCES source_document_versions(id) ON DELETE SET NULL
        );
        """
    )
    db.execute(
        f"""
        INSERT OR IGNORE INTO requirement_analyses_new
          (id, project_id, document_id, version_id, primary_mapping_id, status, analysis_summary, output_json,
           quality_result, testability_score, draft_content_hash, finalized_version_id, finalized_at, finalized_by,
           created_by, created_at)
        SELECT id, project_id, document_id, version_id, {primary_mapping_expr}, status, analysis_summary, output_json,
               quality_result, testability_score, {draft_hash_expr}, {finalized_version_expr}, {finalized_at_expr},
               {finalized_by_expr}, created_by, created_at
        FROM requirement_analyses
        """
    )
    migrated_count = db.execute("SELECT COUNT(*) AS count FROM requirement_analyses_new").fetchone()["count"]
    if migrated_count != source_count:
        db.execute("DROP TABLE IF EXISTS requirement_analyses_new")
        db.execute("PRAGMA foreign_keys=on")
        raise RuntimeError(f"需求分析迁移行数不一致：原表 {source_count} 行，新表 {migrated_count} 行。")

    db.executescript(
        """
        DROP TABLE requirement_analyses;
        ALTER TABLE requirement_analyses_new RENAME TO requirement_analyses;
        """
    )
    db.execute("PRAGMA foreign_keys=on")


def _migrate_agent_model_assignments(db: sqlite3.Connection) -> None:
    exists = db.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'agent_model_assignments'
        """
    ).fetchone()
    if not exists:
        return
    db.execute(
        """
        INSERT OR REPLACE INTO model_assignments (capability_id, model_provider_id, created_at, updated_at)
        SELECT agent_id, model_provider_id, created_at, updated_at
        FROM agent_model_assignments
        """
    )
    db.execute("DROP TABLE agent_model_assignments")


def _migrate_knowledge_query_model_assignment(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE model_assignments
        SET capability_id = 'knowledge_query', updated_at = CURRENT_TIMESTAMP
        WHERE capability_id = 'knowledge_builder'
          AND NOT EXISTS (
            SELECT 1 FROM model_assignments existing WHERE existing.capability_id = 'knowledge_query'
          )
        """
    )
    db.execute("DELETE FROM model_assignments WHERE capability_id = 'knowledge_builder'")


def _migrate_requirement_standardization_model_assignment(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE model_assignments
        SET capability_id = 'requirement_standardization', updated_at = CURRENT_TIMESTAMP
        WHERE capability_id = 'raw_requirement_format_converter'
          AND NOT EXISTS (
            SELECT 1 FROM model_assignments existing WHERE existing.capability_id = 'requirement_standardization'
          )
        """
    )
    db.execute("DELETE FROM model_assignments WHERE capability_id = 'raw_requirement_format_converter'")


def _migrate_remove_retired_model_assignments(db: sqlite3.Connection) -> None:
    """Remove model assignments for capabilities no longer registered in AI_CAPABILITIES."""
    retired_capability_ids = (
        "letter_captcha_recognition",
    )
    for capability_id in retired_capability_ids:
        db.execute("DELETE FROM model_assignments WHERE capability_id = ?", (capability_id,))


def _migrate_stored_paths(db: sqlite3.Connection) -> None:
    for table, columns in {
        "source_document_versions": ("file_path",),
        "source_document_file_mappings": ("source_file_path", "markdown_file_path", "preview_file_path"),
    }.items():
        table_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not table_exists:
            continue
        existing_columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        for column in columns:
            if column not in existing_columns:
                continue
            rows = db.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''").fetchall()
            for row in rows:
                normalized = _normalize_stored_path(row[column])
                if normalized and normalized != row[column]:
                    db.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (normalized, row["id"]))


def _normalize_stored_path(path_value: str) -> str | None:
    stored = store_path(path_value)
    if stored != path_value:
        return stored

    normalized = path_value.replace("\\", "/")
    marker = "/data/projects/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]

    windows_parts = PureWindowsPath(path_value).parts
    if "projects" in windows_parts:
        projects_index = windows_parts.index("projects")
        return Path(*windows_parts[projects_index + 1 :]).as_posix()

    path = Path(path_value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(PROJECT_FILE_STORAGE_ROOT).as_posix()
    except ValueError:
        return path_value


def _sync_seed_password(db: sqlite3.Connection, user_id: str, password: str) -> None:
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (hash_secret(password), user_id),
    )
