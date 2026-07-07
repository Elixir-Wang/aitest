CREATE_SCHEMA_SQL = """\
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

CREATE TABLE IF NOT EXISTS requirement_finalization_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  analysis_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
  summary TEXT NOT NULL DEFAULT '',
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
  include_company_knowledge INTEGER NOT NULL DEFAULT 0,
  generation_scope_type TEXT NOT NULL CHECK(generation_scope_type IN ('all', 'specified')),
  generation_scope_text TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('generating', 'ready_for_review', 'review_completed', 'failed', 'archived')),
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
  review_feedback TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT,
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
  status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'stopping', 'cancelled', 'interrupted', 'completed', 'blocked', 'failed')) DEFAULT 'pending',
  exploration_mode TEXT NOT NULL DEFAULT 'goal' CHECK(exploration_mode IN ('goal', 'autonomous')),
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
  used_requirement_versions_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(conversation_id) REFERENCES knowledge_conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_project_created ON requirement_analysis_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_document_created ON requirement_analysis_runs(document_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requirement_analysis_runs_status ON requirement_analysis_runs(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_requirement_clarification_answers_current ON requirement_clarification_answers(analysis_id, question_id);
CREATE INDEX IF NOT EXISTS idx_requirement_clarification_answers_document ON requirement_clarification_answers(document_id, created_at);
CREATE INDEX IF NOT EXISTS idx_global_knowledge_bases_updated ON global_knowledge_bases(updated_at);
CREATE INDEX IF NOT EXISTS idx_global_knowledge_folders_base_parent ON global_knowledge_folders(knowledge_base_id, parent_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_global_knowledge_vault_files_folder ON global_knowledge_vault_files(folder_id, sort_order, display_name);
CREATE INDEX IF NOT EXISTS idx_knowledge_conversations_project_updated ON knowledge_conversations(project_id, created_by, updated_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_conversation_messages_conversation_created ON knowledge_conversation_messages(conversation_id, created_at);
"""
