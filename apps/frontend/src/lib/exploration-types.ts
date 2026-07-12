import type { AgentPlanStatus } from "@/components/ui/agent-plan";

export type ExplorationMode = "goal" | "autonomous";

export type ProjectScope = "all" | "project";

export type ExplorationEnvironment = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  site_url: string;
  username: string;
  login_strategy: string;
  captcha_strategy: string;
  reuse_auth_state: boolean;
  has_saved_credentials: boolean;
  auth_state_status: string;
  auth_state_expires_at: string | null;
  auth_state_message?: string;
  description: string;
  updated_at: string;
};

export type ExplorationRunSummary = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  title: string;
  status: string;
  exploration_mode: ExplorationMode;
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  goal: string;
  notes: string;
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
  updated_at: string;
  available_actions: string[];
};

export type ExplorationRun = ExplorationRunSummary & {
  artifact_root: string;
  result_summary: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ExplorationStep = {
  id: string;
  type: string;
  title: string;
  detail?: string;
  status?: AgentPlanStatus;
  occurred_at?: string | null;
  artifact_path?: string;
  source?: string;
};

export type ReadableExecutionDisplayKind =
  | "model_analysis"
  | "thought"
  | "agent_run"
  | "navigate"
  | "click"
  | "snapshot"
  | "file_read"
  | "artifact_write"
  | "todo_update"
  | "url_record"
  | "error"
  | "debug";

export type ReadableExecutionField = {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "default" | "success" | "warning" | "danger";
};

export type ReadableExecutionDisplay = {
  kind: ReadableExecutionDisplayKind;
  title: string;
  summary: string;
  fields?: ReadableExecutionField[];
  chips?: string[];
};

export type PersistedExplorationEvent = {
  event_id?: string | number;
  type: string;
  run_id?: string;
  payload?: Record<string, unknown>;
  display?: ReadableExecutionDisplay;
  occurred_at?: string;
  timestamp?: string;
};

export type ExplorationRunDetail = {
  run: ExplorationRun;
  artifact_schema_version: number;
  unsupported_artifact: boolean;
  unsupported_reason: string;
  timeline_events?: PersistedExplorationEvent[];
  modules: Array<{
    id: string;
    module_key: string;
    module_name: string;
    entry_path: string;
    planned_page_count: number;
    explored_page_count: number;
    blocked_page_count: number;
    action_count: number;
    field_count: number;
    state_transition_count: number;
    completion_status: string;
    completion_summary: string;
    pages: Array<{
      id: string;
      title: string;
      url: string;
      entry_path: string;
      yaml_path?: string | null;
      status?: string | null;
      blocker_reason?: string | null;
      recent_event?: string | null;
      structure_summary: string;
      steps?: ExplorationStep[];
    }>;
    elements: Record<string, unknown>[];
    blockers: Array<{
      id: string;
      page_ref: string;
      reason_type: string;
      reason: string;
      suggested_action: string;
      is_blocking: boolean;
    }>;
  }>;
};

export type ExplorationPage = ExplorationRunDetail["modules"][number]["pages"][number];

export type ExplorationReport = {
  run_id: string;
  title: string;
  markdown_content: string;
  change_summary: string;
  artifact_schema_version: number;
  unsupported_artifact: boolean;
  unsupported_reason: string;
};

export type ExplorationStreamEvent = {
  event_id?: number;
  type: string;
  run_id: string;
  payload: Record<string, unknown> | ExplorationRunDetail;
  display?: ReadableExecutionDisplay;
  timeline_event_id?: string;
};

export type ExplorationMonitorPlanStep = {
  step_id: string;
  step_number: number;
  module_name: string;
  action_type: string;
  description: string;
  target_description: string;
  target_selector: string;
  value: string;
  expected_result: string;
  execution_strategy: string;
  is_critical: boolean;
  retry_on_failure: boolean;
  max_retries: number;
};

export type ExplorationMonitorStep = ExplorationMonitorPlanStep & {
  status: AgentPlanStatus;
  total_steps: number;
  attempt: number;
  started_at: string;
  completed_at: string;
  success: boolean | null;
  message: string;
  error: string;
  failure_type: string;
  retryable: boolean;
  matched_element: {
    id: string;
    role: string;
    name: string;
    selector: string;
  };
  page_state: {
    url: string;
    title: string;
    element_count: number;
  };
};

export type ExplorationMonitorEvent = {
  id: string;
  type: string;
  label: string;
  summary: string;
  occurred_at: string;
  status: AgentPlanStatus;
  payload?: Record<string, unknown>;
  display?: ReadableExecutionDisplay;
};

export type ExplorationMonitorState = {
  phase: string;
  plan: {
    plan_id: string;
    goal_summary: string;
    scope_summary: string;
    strategy: string;
    modules: string[];
    estimated_duration_minutes: number | null;
    risk_assessment: string;
    success_criteria: string[];
    total_steps: number;
    steps: ExplorationMonitorPlanStep[];
  } | null;
  steps: ExplorationMonitorStep[];
  events: ExplorationMonitorEvent[];
};
