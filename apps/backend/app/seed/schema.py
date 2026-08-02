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
  default_version_id TEXT,
  status TEXT NOT NULL CHECK(status IN ('active', 'archived')),
  description TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL DEFAULT 'system',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_versions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  version TEXT NOT NULL,
  version_major INTEGER NOT NULL CHECK(version_major >= 0),
  version_minor INTEGER NOT NULL CHECK(version_minor >= 0),
  version_patch INTEGER NOT NULL CHECK(version_patch >= 0),
  name TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  planned_release_at TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  UNIQUE(project_id, version)
);

CREATE INDEX IF NOT EXISTS idx_project_versions_project_semver
  ON project_versions(project_id, version_major DESC, version_minor DESC, version_patch DESC);

CREATE TABLE IF NOT EXISTS knowledge_search_source_settings (
  scope_key TEXT NOT NULL,
  source_type TEXT NOT NULL,
  enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scope_key, source_type)
);

CREATE TABLE IF NOT EXISTS source_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  project_version_id TEXT,
  name TEXT NOT NULL,
  document_type TEXT NOT NULL,
  current_version_id TEXT,
  status TEXT NOT NULL DEFAULT 'collecting',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(project_version_id) REFERENCES project_versions(id) ON DELETE RESTRICT,
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

CREATE TABLE IF NOT EXISTS test_point_generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')),
  input_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  coverage_status TEXT NOT NULL DEFAULT 'pending',
  obligation_count INTEGER NOT NULL DEFAULT 0,
  covered_obligation_count INTEGER NOT NULL DEFAULT 0,
  missing_obligations_json TEXT NOT NULL DEFAULT '[]',
  obligations_json TEXT NOT NULL DEFAULT '[]',
  unsupported_assumptions_json TEXT NOT NULL DEFAULT '[]',
  supplement_round INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_test_point_generation_version
  ON test_point_generation_runs(document_id, requirement_version_id);

CREATE TABLE IF NOT EXISTS test_points (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  generation_run_id TEXT NOT NULL,
  point_key TEXT NOT NULL,
  title TEXT NOT NULL,
  module TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'P1',
  description TEXT NOT NULL DEFAULT '',
  preconditions_json TEXT NOT NULL DEFAULT '[]',
  verification_points_json TEXT NOT NULL DEFAULT '[]',
  source_refs_json TEXT NOT NULL DEFAULT '[]',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE,
  FOREIGN KEY(generation_run_id) REFERENCES test_point_generation_runs(id) ON DELETE CASCADE,
  UNIQUE(requirement_version_id, point_key)
);

CREATE INDEX IF NOT EXISTS idx_test_points_document_version
  ON test_points(document_id, requirement_version_id);

CREATE TABLE IF NOT EXISTS test_point_requirement_obligations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  obligation_key TEXT NOT NULL,
  source_section TEXT NOT NULL,
  statement TEXT NOT NULL,
  obligation_type TEXT NOT NULL,
  modules_json TEXT NOT NULL DEFAULT '[]',
  thresholds_json TEXT NOT NULL DEFAULT '[]',
  explicit INTEGER NOT NULL DEFAULT 1,
  test_required INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES source_documents(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE,
  UNIQUE(requirement_version_id, obligation_key)
);

CREATE INDEX IF NOT EXISTS idx_test_point_obligations_document_version
  ON test_point_requirement_obligations(document_id, requirement_version_id);

CREATE TABLE IF NOT EXISTS test_point_obligations (
  test_point_id TEXT NOT NULL,
  obligation_id TEXT NOT NULL,
  requirement_version_id TEXT NOT NULL,
  PRIMARY KEY(test_point_id, obligation_id),
  FOREIGN KEY(test_point_id) REFERENCES test_points(id) ON DELETE CASCADE,
  FOREIGN KEY(obligation_id) REFERENCES test_point_requirement_obligations(id) ON DELETE CASCADE,
  FOREIGN KEY(requirement_version_id) REFERENCES source_document_versions(id) ON DELETE CASCADE
);

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
  test_description TEXT NOT NULL DEFAULT '',
  module TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT '',
  display_order INTEGER NOT NULL DEFAULT 0,
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

CREATE INDEX IF NOT EXISTS idx_test_cases_set_display_order
  ON test_cases(test_case_set_id, display_order);

CREATE TABLE IF NOT EXISTS manual_test_cases (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  title TEXT NOT NULL,
  preconditions TEXT NOT NULL DEFAULT '',
  steps_json TEXT NOT NULL DEFAULT '[]',
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_manual_test_cases_project_updated
  ON manual_test_cases(project_id, updated_at);

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

CREATE TABLE IF NOT EXISTS api_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK(source_type IN ('url', 'file')),
  source_url TEXT NOT NULL DEFAULT '',
  file_path TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('parsed', 'failed')),
  endpoint_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_documents_project_created
  ON api_documents(project_id, created_at);

CREATE TABLE IF NOT EXISTS api_endpoints (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  normalized_path TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  parameters_json TEXT NOT NULL DEFAULT '[]',
  request_body_json TEXT NOT NULL DEFAULT '{}',
  responses_json TEXT NOT NULL DEFAULT '{}',
  auth_json TEXT NOT NULL DEFAULT '{}',
  source_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES api_documents(id) ON DELETE SET NULL,
  UNIQUE(project_id, method, normalized_path)
);

CREATE INDEX IF NOT EXISTS idx_api_endpoints_project_method
  ON api_endpoints(project_id, method);

CREATE TABLE IF NOT EXISTS api_test_environments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  linked_ui_environment_id TEXT,
  name TEXT NOT NULL,
  api_base_url TEXT NOT NULL,
  username TEXT NOT NULL DEFAULT '',
  password_encrypted TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL DEFAULT '',
  auth_type TEXT NOT NULL CHECK(auth_type IN ('none', 'account_password', 'cybertron_agent')) DEFAULT 'none',
  auth_config_json TEXT NOT NULL DEFAULT '{}',
  variables_json TEXT NOT NULL DEFAULT '{}',
  default_headers_json TEXT NOT NULL DEFAULT '{}',
  timeout_seconds INTEGER NOT NULL DEFAULT 30,
  verify_ssl INTEGER NOT NULL DEFAULT 1,
  auth_state_ttl_seconds INTEGER NOT NULL DEFAULT 86400,
  description TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(linked_ui_environment_id) REFERENCES project_environments(id) ON DELETE SET NULL,
  UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS api_generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  api_environment_id TEXT,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'partial_success', 'failed', 'cancelled', 'interrupted')),
  endpoint_ids_json TEXT NOT NULL DEFAULT '[]',
  source_test_case_ids_json TEXT NOT NULL DEFAULT '[]',
  generation_goal TEXT NOT NULL DEFAULT '',
  options_json TEXT NOT NULL DEFAULT '{}',
  result_summary_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_generation_runs_project_created
  ON api_generation_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS api_script_generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
  endpoint_ids_json TEXT NOT NULL DEFAULT '[]',
  api_environment_id TEXT,
  force INTEGER NOT NULL DEFAULT 0,
  suite_path TEXT NOT NULL DEFAULT '',
  changed_files_json TEXT NOT NULL DEFAULT '[]',
  result_summary_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_script_generation_runs_project_created
  ON api_script_generation_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS api_generation_items (
  id TEXT PRIMARY KEY,
  generation_run_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed')) DEFAULT 'queued',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  generated_case_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NOT NULL DEFAULT '',
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
  UNIQUE(generation_run_id, endpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_api_generation_items_run_status
  ON api_generation_items(generation_run_id, status);

CREATE TABLE IF NOT EXISTS api_generation_item_attempts (
  id TEXT PRIMARY KEY,
  generation_item_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')) DEFAULT 'running',
  generated_case_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NOT NULL DEFAULT '',
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(generation_item_id) REFERENCES api_generation_items(id) ON DELETE CASCADE,
  UNIQUE(generation_item_id, attempt_no)
);

CREATE INDEX IF NOT EXISTS idx_api_generation_item_attempts_item
  ON api_generation_item_attempts(generation_item_id, attempt_no);

CREATE TABLE IF NOT EXISTS api_test_case_sets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('draft', 'generating', 'ready', 'failed', 'archived')) DEFAULT 'draft',
  case_count INTEGER NOT NULL DEFAULT 0,
  latest_generation_run_id TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(latest_generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_test_case_sets_project_updated
  ON api_test_case_sets(project_id, updated_at);

CREATE TABLE IF NOT EXISTS api_test_cases (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  endpoint_id TEXT,
  source_test_case_id TEXT,
  generation_run_id TEXT,
  generation_item_id TEXT,
  generation_attempt_id TEXT,
  title TEXT NOT NULL,
  test_point_key TEXT NOT NULL DEFAULT '',
  oracle_status TEXT NOT NULL DEFAULT 'confirmed' CHECK(oracle_status IN ('confirmed', 'inferred', 'needs_confirmation')),
  priority TEXT NOT NULL DEFAULT 'P2',
  coverage TEXT NOT NULL DEFAULT 'positive',
  source TEXT NOT NULL CHECK(source IN ('ai_generated', 'manual', 'approved_test_case')) DEFAULT 'ai_generated',
  preconditions_json TEXT NOT NULL DEFAULT '[]',
  request_json TEXT NOT NULL DEFAULT '{}',
  test_data_json TEXT NOT NULL DEFAULT '{}',
  expected_json TEXT NOT NULL DEFAULT '{}',
  assertions_json TEXT NOT NULL DEFAULT '[]',
  variables_json TEXT NOT NULL DEFAULT '{}',
  data_origin_json TEXT NOT NULL DEFAULT '{}',
  data_file_path TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(source_test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL,
  FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL,
  FOREIGN KEY(generation_item_id) REFERENCES api_generation_items(id) ON DELETE SET NULL,
  FOREIGN KEY(generation_attempt_id) REFERENCES api_generation_item_attempts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_test_cases_project_endpoint
  ON api_test_cases(project_id, endpoint_id);

CREATE TABLE IF NOT EXISTS api_test_case_versions (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL DEFAULT '{}',
  change_source TEXT NOT NULL DEFAULT 'oracle_approval',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE,
  UNIQUE(case_id, version)
);

CREATE INDEX IF NOT EXISTS idx_api_test_case_versions_case
  ON api_test_case_versions(case_id, version);

CREATE TABLE IF NOT EXISTS api_endpoint_oracle_facts (
  id TEXT PRIMARY KEY,
  endpoint_id TEXT NOT NULL,
  test_point_key TEXT NOT NULL,
  assertions_json TEXT NOT NULL DEFAULT '[]',
  evidence_run_ids_json TEXT NOT NULL DEFAULT '[]',
  approved_by TEXT NOT NULL,
  approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
  UNIQUE(endpoint_id, test_point_key)
);

CREATE TABLE IF NOT EXISTS api_test_scripts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  endpoint_id TEXT,
  api_test_case_id TEXT,
  test_case_id TEXT,
  generation_run_id TEXT,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'needs_input', 'failed')),
  suite_path TEXT NOT NULL,
  test_file_path TEXT NOT NULL,
  data_file_path TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'python',
  framework TEXT NOT NULL DEFAULT 'pytest_requests',
  source_hash TEXT NOT NULL DEFAULT '',
  case_count INTEGER NOT NULL DEFAULT 0,
  manual_modified INTEGER NOT NULL DEFAULT 0,
  last_run_status TEXT NOT NULL DEFAULT '',
  last_run_at TEXT,
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(api_test_case_id) REFERENCES api_test_cases(id) ON DELETE SET NULL,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL,
  FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_scripts_project_updated
  ON api_test_scripts(project_id, updated_at);

CREATE TABLE IF NOT EXISTS api_automation_runs (
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
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_runs_project_created
  ON api_automation_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS api_repair_sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  source_run_id TEXT NOT NULL,
  current_run_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('active', 'passed', 'closed', 'failed')) DEFAULT 'active',
  current_revision INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(source_run_id) REFERENCES api_automation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(current_run_id) REFERENCES api_automation_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_repair_sessions_project_updated
  ON api_repair_sessions(project_id, updated_at);

CREATE TABLE IF NOT EXISTS api_repair_attempts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  attempt_number INTEGER NOT NULL,
  base_run_id TEXT NOT NULL,
  base_revision INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  user_context TEXT NOT NULL DEFAULT '',
  diagnosis_json TEXT NOT NULL DEFAULT '{}',
  validation_json TEXT NOT NULL DEFAULT '{}',
  decision TEXT NOT NULL DEFAULT '',
  applied_run_id TEXT,
  error_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(session_id, attempt_number),
  FOREIGN KEY(session_id) REFERENCES api_repair_sessions(id) ON DELETE CASCADE,
  FOREIGN KEY(base_run_id) REFERENCES api_automation_runs(id) ON DELETE CASCADE,
  FOREIGN KEY(applied_run_id) REFERENCES api_automation_runs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_repair_attempts_session_number
  ON api_repair_attempts(session_id, attempt_number);

CREATE TABLE IF NOT EXISTS api_oracle_proposals (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  test_point_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'superseded')) DEFAULT 'pending',
  current_snapshot_json TEXT NOT NULL DEFAULT '{}',
  proposed_snapshot_json TEXT NOT NULL DEFAULT '{}',
  reasoning TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  review_scope TEXT NOT NULL DEFAULT '',
  review_comment TEXT NOT NULL DEFAULT '',
  reviewed_by TEXT,
  reviewed_at TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE,
  FOREIGN KEY(case_id) REFERENCES api_test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(run_id) REFERENCES api_automation_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_oracle_proposals_project_status
  ON api_oracle_proposals(project_id, status, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS idx_api_oracle_proposals_run_case
  ON api_oracle_proposals(run_id, case_id);

CREATE TABLE IF NOT EXISTS performance_tests (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  target_type TEXT NOT NULL CHECK(target_type IN ('endpoint')) DEFAULT 'endpoint',
  endpoint_id TEXT,
  api_environment_id TEXT,
  request_config_json TEXT NOT NULL DEFAULT '{}',
  load_config_json TEXT NOT NULL DEFAULT '{}',
  data_config_json TEXT NOT NULL DEFAULT '{}',
  circuit_breaker_json TEXT NOT NULL DEFAULT '{}',
  performance_goal_json TEXT NOT NULL DEFAULT '{}',
  success_rules_json TEXT NOT NULL DEFAULT '[]',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL,
  UNIQUE(project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_performance_tests_project_updated
  ON performance_tests(project_id, updated_at);

CREATE TABLE IF NOT EXISTS performance_test_scripts (
  id TEXT PRIMARY KEY,
  performance_test_id TEXT NOT NULL UNIQUE,
  project_id TEXT NOT NULL,
  generation_source TEXT NOT NULL CHECK(generation_source IN ('ai_plan', 'default_plan', 'user_edited')),
  model_id TEXT NOT NULL DEFAULT '',
  prompt_version TEXT NOT NULL DEFAULT '',
  plan_json TEXT NOT NULL DEFAULT '{}',
  code TEXT NOT NULL,
  assumptions_json TEXT NOT NULL DEFAULT '[]',
  required_runtime_variables_json TEXT NOT NULL DEFAULT '[]',
  validation_status TEXT NOT NULL CHECK(validation_status IN ('generating', 'validation_failed', 'valid')),
  validation_result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(performance_test_id) REFERENCES performance_tests(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS performance_test_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  performance_test_id TEXT NOT NULL,
  script_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('created', 'starting', 'running', 'stopping', 'completed', 'stopped', 'failed', 'cancelled')),
  worker_id TEXT NOT NULL DEFAULT '',
  load_config_json TEXT NOT NULL DEFAULT '{}',
  runtime_config_json TEXT NOT NULL DEFAULT '{}',
  latest_summary_json TEXT NOT NULL DEFAULT '{}',
  error_code TEXT NOT NULL DEFAULT '',
  error_message TEXT NOT NULL DEFAULT '',
  trace_id TEXT NOT NULL DEFAULT '',
  report_directory TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(performance_test_id) REFERENCES performance_tests(id) ON DELETE CASCADE,
  FOREIGN KEY(script_id) REFERENCES performance_test_scripts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_performance_test_runs_project_created
  ON performance_test_runs(project_id, created_at);

CREATE TABLE IF NOT EXISTS performance_analysis_sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('collecting', 'analyzing', 'waiting_approval', 'failed', 'rejected')),
  analysis_status TEXT NOT NULL DEFAULT 'collecting',
  analysis_stage TEXT NOT NULL DEFAULT 'evidence_collection',
  repair_status TEXT NOT NULL DEFAULT 'not_applicable',
  analysis_version INTEGER NOT NULL,
  category TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  direct_cause TEXT NOT NULL DEFAULT '',
  root_cause TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  evidence_json TEXT NOT NULL DEFAULT '[]',
  missing_evidence_json TEXT NOT NULL DEFAULT '[]',
  proposal_json TEXT NOT NULL DEFAULT '{}',
  metric_snapshot_json TEXT NOT NULL DEFAULT '{}',
  report_snapshot_json TEXT NOT NULL DEFAULT '{}',
  calculator_version TEXT NOT NULL DEFAULT '',
  prompt_version TEXT NOT NULL DEFAULT '',
  source_fingerprint TEXT NOT NULL DEFAULT '',
  generation_mode TEXT NOT NULL DEFAULT '',
  analysis_attempts_json TEXT NOT NULL DEFAULT '[]',
  audience TEXT NOT NULL DEFAULT 'engineer',
  application_status TEXT NOT NULL DEFAULT 'not_requested',
  selected_change_ids_json TEXT NOT NULL DEFAULT '[]',
  preflight_json TEXT NOT NULL DEFAULT '{}',
  applied_script_id TEXT NOT NULL DEFAULT '',
  applied_run_id TEXT NOT NULL DEFAULT '',
  applied_by TEXT NOT NULL DEFAULT '',
  applied_at TEXT,
  model_name TEXT NOT NULL DEFAULT '',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(run_id) REFERENCES performance_test_runs(id) ON DELETE CASCADE,
  UNIQUE(run_id, analysis_version)
);

CREATE INDEX IF NOT EXISTS idx_performance_analysis_run_status
  ON performance_analysis_sessions(run_id, status);

CREATE INDEX IF NOT EXISTS idx_performance_analysis_project_created
  ON performance_analysis_sessions(project_id, created_at);

CREATE TABLE IF NOT EXISTS performance_test_run_stats (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  sampled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_count INTEGER NOT NULL DEFAULT 0,
  request_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  requests_per_second REAL NOT NULL DEFAULT 0,
  failure_rate REAL NOT NULL DEFAULT 0,
  average_response_time_ms REAL NOT NULL DEFAULT 0,
  p50_response_time_ms REAL NOT NULL DEFAULT 0,
  p95_response_time_ms REAL NOT NULL DEFAULT 0,
  p99_response_time_ms REAL NOT NULL DEFAULT 0,
  stats_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(run_id) REFERENCES performance_test_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_performance_test_run_stats_run_sampled
  ON performance_test_run_stats(run_id, sampled_at);

CREATE TABLE IF NOT EXISTS performance_test_run_failures (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  request_name TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  last_occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sample_status_code INTEGER,
  sample_response_excerpt TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(run_id) REFERENCES performance_test_runs(id) ON DELETE CASCADE,
  UNIQUE(run_id, request_name, method, reason)
);

CREATE TABLE IF NOT EXISTS performance_test_run_exceptions (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  request_name TEXT NOT NULL DEFAULT '',
  exception_type TEXT NOT NULL,
  message TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1,
  last_occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES performance_test_runs(id) ON DELETE CASCADE,
  UNIQUE(run_id, request_name, exception_type, message)
);

CREATE TABLE IF NOT EXISTS performance_test_run_events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'info',
  message TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}',
  trace_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES performance_test_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_performance_test_run_events_run_created
  ON performance_test_run_events(run_id, created_at);

CREATE TABLE IF NOT EXISTS performance_scenarios (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  api_environment_id TEXT NOT NULL,
  definition_version INTEGER NOT NULL DEFAULT 1,
  scenario_definition_json TEXT NOT NULL,
  load_profile_json TEXT NOT NULL,
  data_source_json TEXT NOT NULL,
  quality_gate_json TEXT NOT NULL,
  safety_policy_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE RESTRICT,
  UNIQUE(project_id, name)
);

CREATE INDEX IF NOT EXISTS idx_performance_scenarios_project_updated
  ON performance_scenarios(project_id, updated_at);

CREATE TABLE IF NOT EXISTS performance_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  scenario_id TEXT NOT NULL,
  process_status TEXT NOT NULL CHECK(process_status IN ('created', 'validating', 'starting', 'warming_up', 'measuring', 'stopping', 'finished')) DEFAULT 'created',
  stop_reason TEXT NOT NULL DEFAULT '',
  quality_status TEXT NOT NULL CHECK(quality_status IN ('passed', 'failed', 'not_configured', 'not_evaluated')) DEFAULT 'not_evaluated',
  run_snapshot_json TEXT NOT NULL,
  latest_summary_json TEXT NOT NULL DEFAULT '{}',
  script_hash TEXT NOT NULL DEFAULT '',
  locust_version TEXT NOT NULL DEFAULT '',
  exit_code INTEGER,
  error_code TEXT NOT NULL DEFAULT '',
  error_message TEXT NOT NULL DEFAULT '',
  report_directory TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  measurement_started_at TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(scenario_id) REFERENCES performance_scenarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS performance_run_gate_results (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  metric TEXT NOT NULL,
  operator TEXT NOT NULL,
  threshold REAL,
  actual REAL,
  status TEXT NOT NULL CHECK(status IN ('passed', 'failed', 'not_evaluated')),
  reason TEXT NOT NULL DEFAULT '',
  evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(run_id) REFERENCES performance_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_scenarios (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'archived')) DEFAULT 'draft',
  variables_json TEXT NOT NULL DEFAULT '{}',
  revision INTEGER NOT NULL DEFAULT 0,
  published_snapshot_json TEXT NOT NULL DEFAULT '{}',
  published_hash TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_scenario_steps (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  step_type TEXT NOT NULL DEFAULT 'api_request',
  endpoint_id TEXT,
  api_test_case_id TEXT,
  step_order INTEGER NOT NULL DEFAULT 0,
  name TEXT NOT NULL DEFAULT '',
  request_overrides_json TEXT NOT NULL DEFAULT '{}',
  bindings_json TEXT NOT NULL DEFAULT '[]',
  extractors_json TEXT NOT NULL DEFAULT '[]',
  assertions_json TEXT NOT NULL DEFAULT '[]',
  control_config_json TEXT NOT NULL DEFAULT '{}',
  on_failure TEXT NOT NULL CHECK(on_failure IN ('stop', 'continue', 'always_run')) DEFAULT 'stop',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(scenario_id) REFERENCES api_scenarios(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(api_test_case_id) REFERENCES api_test_cases(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS api_scenario_revisions (
  id TEXT PRIMARY KEY,
  scenario_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  published_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scenario_id, revision),
  FOREIGN KEY(scenario_id) REFERENCES api_scenarios(id) ON DELETE CASCADE,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_scenario_revisions_scenario_revision
  ON api_scenario_revisions(scenario_id, revision DESC);

CREATE TABLE IF NOT EXISTS api_scenario_ai_plans (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  scenario_id TEXT,
  expected_revision INTEGER,
  goal TEXT NOT NULL,
  request_json TEXT NOT NULL DEFAULT '{}',
  proposal_json TEXT NOT NULL DEFAULT '{}',
  review_json TEXT NOT NULL DEFAULT '{}',
  review_revision INTEGER NOT NULL DEFAULT 0,
  generation_meta_json TEXT NOT NULL DEFAULT '{}',
  asset_fingerprint TEXT NOT NULL DEFAULT '',
  plan_json TEXT NOT NULL DEFAULT '{}',
  validation_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK(status IN ('preview', 'applied', 'discarded', 'expired')) DEFAULT 'preview',
  lifecycle_status TEXT NOT NULL DEFAULT 'completed',
  error_message TEXT NOT NULL DEFAULT '',
  model_provider TEXT NOT NULL DEFAULT '',
  model_name TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  applied_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  applied_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(scenario_id) REFERENCES api_scenarios(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_scenario_ai_plans_project_created
  ON api_scenario_ai_plans(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS exploration_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  requirement_doc_id TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending', 'queued', 'running', 'stopping', 'cancelled', 'interrupted', 'completed', 'blocked', 'failed')) DEFAULT 'pending',
  exploration_mode TEXT NOT NULL DEFAULT 'goal' CHECK(exploration_mode IN ('goal', 'autonomous', 'loop')),
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
  retention_days INTEGER NOT NULL DEFAULT 10,
  max_rows INTEGER NOT NULL DEFAULT 100000,
  protect_high_risk INTEGER NOT NULL DEFAULT 1,
  updated_by TEXT NOT NULL DEFAULT 'system',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS retention_cleanup_state (
  job_name TEXT PRIMARY KEY,
  last_success_at TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS ui_automation_generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  test_case_id TEXT,
  manual_test_case_id TEXT,
  environment_id TEXT NOT NULL,
  exploration_run_id TEXT NOT NULL DEFAULT '',
  task_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'queued',
  suite_path TEXT NOT NULL DEFAULT '',
  changed_files_json TEXT NOT NULL DEFAULT '[]',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE,
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ui_automation_assets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  test_case_id TEXT,
  manual_test_case_id TEXT,
  source_version INTEGER NOT NULL DEFAULT 1,
  generation_run_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  pytest_node_id TEXT NOT NULL,
  suite_path TEXT NOT NULL,
  test_file_path TEXT NOT NULL,
  data_file_path TEXT NOT NULL,
  plan_file_path TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(manual_test_case_id) REFERENCES manual_test_cases(id) ON DELETE CASCADE,
  FOREIGN KEY(generation_run_id) REFERENCES ui_automation_generation_runs(id) ON DELETE CASCADE,
  CHECK ((test_case_id IS NOT NULL) != (manual_test_case_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS ui_automation_execution_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  environment_id TEXT NOT NULL,
  task_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'queued',
  run_dir TEXT NOT NULL DEFAULT '',
  result_json TEXT NOT NULL DEFAULT '{}',
  stdout_path TEXT NOT NULL DEFAULT '',
  stderr_path TEXT NOT NULL DEFAULT '',
  screenshot_paths_json TEXT NOT NULL DEFAULT '[]',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(asset_id) REFERENCES ui_automation_assets(id) ON DELETE CASCADE,
  FOREIGN KEY(environment_id) REFERENCES project_environments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ui_generation_project_created ON ui_automation_generation_runs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ui_assets_project_updated ON ui_automation_assets(project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_ui_execution_project_created ON ui_automation_execution_runs(project_id, created_at);

"""
