"use client";

import { useAuthStore } from "@/stores/auth-store";

function normalizeApiBaseUrl(value: string) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export const API_BASE_URL = normalizeApiBaseUrl(
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:18000/api/v1",
);

type ApiEnvelope<T> = {
  data: T;
  trace_id: string;
};

export class ApiRequestError extends Error {
  code: string;
  status: number;
  traceId: string;
  detail: unknown;

  constructor(
    message: string,
    {
      code = "",
      detail = null,
      status,
      traceId = "",
    }: {
      code?: string;
      detail?: unknown;
      status: number;
      traceId?: string;
    },
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.traceId = traceId;
    this.detail = detail;
  }
}

export type ApiRole = "admin" | "tester" | "guest";
export type ApiStatus = "enabled" | "disabled";

export type ApiUser = {
  id: string;
  username: string;
  email: string;
  nickname: string | null;
  role: ApiRole;
  status: ApiStatus;
  project_scope: string;
  description: string;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
  available_actions: string[];
};

export type ApiModelProvider = {
  id: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
  description: string;
  status: ApiStatus;
  health_status: "unknown" | "healthy" | "unhealthy" | "timeout" | "testing";
  last_test_at: string | null;
  last_test_message: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

export type ApiModelAssignment = {
  capability_id: string;
  capability_name: string;
  capability_description: string;
  model_provider_id: string | null;
  provider: string | null;
  model: string | null;
  base_url: string | null;
  api_key: string | null;
  model_status: ApiStatus | null;
  updated_at: string | null;
};

export type ApiProject = {
  id: string;
  name: string;
  description: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

export type ApiRequirementDocument = {
  id: string;
  project_id: string;
  name: string;
  document_type: string;
  status: string;
  current_version_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  current_version: {
    id: string;
    version_no: number;
    file_path: string;
    source_action: string;
    change_summary: string;
    diff_summary: string;
    created_by: string;
    created_at: string;
  } | null;
};

export type ApiExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  title: string;
  test_description: string;
  status: string;
  exploration_mode: "goal" | "autonomous" | "loop";
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  goal: string;
  notes: string;
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

export type ApiTestCaseGenerationScopeType = "all" | "specified";

type ApiTestCaseGenerationRun = {
  id: string;
  test_case_set_id: string;
  task_id: string;
  status: string;
  input_snapshot: Record<string, unknown>;
  error_message: string;
  created_at: string;
  finished_at: string | null;
};

export type ApiTestCaseStep = {
  action: string;
  step?: string;
  description?: string;
  expected_result: string;
};

export type ApiTestCase = {
  id: string;
  test_case_set_id: string;
  project_id: string;
  title: string;
  module: string;
  priority: string;
  preconditions: string;
  steps: ApiTestCaseStep[];
  expected_result: string;
  status: string;
  review_feedback: string;
  reviewed_by: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiManualTestCase = {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  preconditions: string;
  steps: ApiTestCaseStep[];
  notes: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ApiManualTestCaseCreate = {
  title: string;
  preconditions: string;
  steps: ApiTestCaseStep[];
  notes: string;
};

export type ApiManualTestCaseAiGenerateRequest = {
  description: string;
  include_exploration_artifacts: boolean;
};

export type ApiManualTestCaseAiGenerateResult = {
  title: string;
  preconditions: string;
  steps: ApiTestCaseStep[];
  generation_notes: string[];
  source_summary: {
    description_used: boolean;
    exploration_artifacts_requested: boolean;
    exploration_artifacts_used: boolean;
    page_count: number;
    operation_count: number;
    truncated: boolean;
  };
};

export type ApiTestCaseReviewStats = {
  case_count: number;
  approved_count: number;
  rejected_count: number;
  pending_count: number;
  reviewed_count: number;
  adoption_rate: number;
  review_progress: number;
};

export type ApiTestCaseReviewUpdate = {
  status: "ready_for_review" | "approved" | "rejected";
  review_feedback: string;
  preconditions?: string;
  steps?: ApiTestCaseStep[];
  expected_result?: string;
};

export type ApiTestCaseReviewResult = {
  case: ApiTestCase;
  review_stats: ApiTestCaseReviewStats;
  knowledge_record: {
    record_id: string;
    file_id: string;
    file_name: string;
    status: "active" | "inactive";
  } | null;
};

export type ApiTestCaseSet = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  generation_scope_type: ApiTestCaseGenerationScopeType;
  generation_scope_text: string;
  notes: string;
  status: string;
  status_label: string;
  case_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  generation_run: ApiTestCaseGenerationRun | null;
  review_stats: ApiTestCaseReviewStats;
  cases: ApiTestCase[];
};

export type ApiTestCaseSetCreate = {
  name: string;
  requirement_doc_id: string;
  generation_scope_type: ApiTestCaseGenerationScopeType;
  generation_scope_text: string;
  notes: string;
};

export type UiAutomationGenerationRun = {
  id: string;
  project_id: string;
  test_case_id: string;
  environment_id: string;
  exploration_run_id: string;
  task_id: string;
  status: string;
  suite_path: string;
  changed_files: string[];
  error_message: string;
  created_by: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UiAutomationAsset = {
  id: string;
  project_id: string;
  test_case_id: string;
  source_version: number;
  generation_run_id: string;
  status: string;
  pytest_node_id: string;
  suite_path: string;
  test_file_path: string;
  data_file_path: string;
  plan_file_path: string;
  source_hash: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  source_title?: string;
  latest_generation_run?: UiAutomationGenerationRun | null;
  latest_execution_run?: UiAutomationExecutionRun | null;
  locator_summary?: { required: number; available: number; missing: string[] };
};

export type UiAutomationExecutionRun = {
  id: string;
  project_id: string;
  asset_id: string;
  environment_id: string;
  status: string;
  run_dir: string;
  result: Record<string, unknown>;
  stdout_path: string;
  stderr_path: string;
  trace_path: string;
  video_path: string;
  screenshot_paths: string[];
  error_message: string;
  created_by: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UiAutomationRunLogs = {
  stdout: string;
  stderr: string;
};

export type UiAutomationLiveView = {
  status: "waiting" | "starting" | "ready" | "unavailable" | "ended";
  message: string;
  stream_path: string;
  width: number;
  height: number;
};

export type ApiTestPoint = {
  id: string;
  project_id: string;
  document_id: string;
  requirement_version_id: string;
  generation_run_id: string;
  title: string;
  module: string;
  category: string;
  priority: string;
  description: string;
  preconditions: string[];
  verification_points: string[];
  source_refs: string[];
  requirement_obligations: ApiTestPointRequirementObligation[];
  notes: string;
  created_at: string;
  updated_at: string;
};

export type ApiTestPointGenerationRun = {
  id: string;
  task_id: string;
  requirement_version_id: string;
  status: string;
  status_label?: string;
  input_snapshot: Record<string, unknown>;
  error_message: string;
  coverage_status?: "pending" | "complete" | "incomplete" | "invalid";
  obligation_count?: number;
  covered_obligation_count?: number;
  missing_obligations?: string[];
  unsupported_assumptions?: string[];
  supplement_round?: number;
  created_at: string;
  finished_at: string | null;
};

export type ApiTestPointRequirementObligation = {
  obligation_key: string;
  source_section: string;
  statement: string;
};

export type ApiTestPointCoverageSummary = {
  status: "pending" | "complete" | "incomplete" | "invalid";
  obligation_count: number;
  covered_obligation_count: number;
  missing_obligations: ApiTestPointRequirementObligation[];
  unsupported_assumptions: string[];
  supplement_round: number;
};

export type ApiTestPointOverview = {
  requirement_version_id: string | null;
  requirement_version_no: number | null;
  run: ApiTestPointGenerationRun | null;
  points: ApiTestPoint[];
  markdown_content: string;
  coverage_summary: ApiTestPointCoverageSummary;
};

type ApiDashboardMetric = {
  label: string;
  value: string;
  helper: string;
};

export type ApiDashboardTrendPoint = {
  date: string;
  caseAssets: number;
  adoptedCases: number;
  automationCases: number;
};

export type ApiDashboardOverview = {
  scope: "all" | "project";
  project_id: string | null;
  project_name: string | null;
  metrics: ApiDashboardMetric[];
  trend: ApiDashboardTrendPoint[];
};

export type ApiOperationLogListItem = {
  id: string;
  log_type: string;
  module: string;
  action: string;
  object_type: string;
  object_id: string | null;
  object_name: string;
  project_id: string | null;
  actor_id: string;
  actor_name: string;
  source: string;
  result: string;
  failure_reason: string;
  summary: string;
  task_id: string | null;
  created_at: string;
};

export type ApiOperationLogDetail = ApiOperationLogListItem & {
  before: unknown;
  after: unknown;
  artifact_path: string[];
  request_id: string;
  ip_address: string;
  user_agent: string;
};

export type ApiOperationLogList = {
  items: ApiOperationLogListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiOperationLogFilterOptions = {
  modules: string[];
  actions: string[];
  results: string[];
  log_types: string[];
};

type ApiAvailableAction = {
  key: string;
  label: string;
  enabled: boolean;
  disabled_reason: string;
  risk_level: "normal" | "warning" | "danger";
  confirm_required: boolean;
};

export type ApiKnowledgeQueryResult = {
  conversation: ApiKnowledgeConversation | null;
  messages: ApiKnowledgeConversationMessage[];
  answer: string;
};

export type ApiKnowledgeConversation = {
  id: string;
  project_id: string;
  title: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type ApiKnowledgeConversationMessage = {
  id: string;
  conversation_id: string;
  role: "assistant" | "user";
  content: string;
  created_at: string;
};

export type ApiKnowledgeConversationDetail = {
  conversation: ApiKnowledgeConversation;
  messages: ApiKnowledgeConversationMessage[];
};

type ApiTaskStatusGroup = "running" | "waiting" | "failed" | "completed";

export type ApiTaskItem = {
  id: string;
  source_type: string;
  source_id: string;
  project_id: string;
  project_name: string;
  module: string;
  module_label: string;
  title: string;
  status: string;
  status_label: string;
  status_group: ApiTaskStatusGroup;
  summary: string;
  created_at: string;
  updated_at: string;
  detail_url: string;
};

export type ApiTaskList = {
  items: ApiTaskItem[];
  total: number;
  page: number;
  page_size: number;
};

export type ApiCompanyKnowledgeBase = {
  id: string;
  name: string;
  description: string;
  status: "processing" | "available" | "conversion_failed";
  status_label: string;
  root_folder_id: string;
  file_count: number;
  created_at: string;
  updated_at: string;
  available_actions: ApiAvailableAction[];
};

export type ApiCompanyKnowledgeFile = {
  id: string;
  type: "file";
  knowledge_base_id: string;
  folder_id: string;
  name: string;
  original_filename: string;
  display_name: string;
  file_type: string;
  file_size: number;
  conversion_status: "queued" | "running" | "success" | "failed";
  conversion_summary: string;
  markdown_content?: string;
  raw_path?: string;
  markdown_path?: string;
  created_at: string;
  updated_at: string;
};

export type ApiCompanyKnowledgeFolder = {
  id: string;
  type: "folder";
  name: string;
  parent_id: string | null;
  is_root: boolean;
  children: ApiCompanyKnowledgeTreeNode[];
};

export type ApiCompanyKnowledgeTreeNode = ApiCompanyKnowledgeFolder | ApiCompanyKnowledgeFile;

export type ApiCompanyKnowledgeBaseList = {
  items: ApiCompanyKnowledgeBase[];
};

export type ApiCompanyKnowledgeTree = {
  base: ApiCompanyKnowledgeBase;
  root: ApiCompanyKnowledgeFolder;
};

export type ApiCompanyKnowledgeUploadResult = {
  files: ApiCompanyKnowledgeFile[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function apiErrorMessageFromPayload(payload: unknown, fallbackMessage = "请求失败，请稍后重试。") {
  const detail = isRecord(payload) ? payload.detail : null;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!isRecord(item)) return "";
        const message = typeof item.msg === "string" ? item.msg : "";
        const location = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
        return message && location ? `${location}: ${message}` : message;
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join("；");
  }
  return (
    (isRecord(detail) && typeof detail.message === "string" ? detail.message : "") ||
    (typeof detail === "string" ? detail : "") ||
    fallbackMessage
  );
}

function apiErrorCodeFromPayload(payload: unknown) {
  const detail = isRecord(payload) ? payload.detail : null;
  return isRecord(detail) && typeof detail.code === "string" ? detail.code : "";
}

function apiErrorFromResponse(
  response: Response,
  payload: unknown,
  fallbackMessage = "请求失败，请稍后重试。",
): ApiRequestError {
  const detail = isRecord(payload) ? payload.detail : null;
  const traceId =
    (isRecord(payload) && typeof payload.trace_id === "string" ? payload.trace_id : "") ||
    response.headers.get("x-trace-id") ||
    "";

  return new ApiRequestError(apiErrorMessageFromPayload(payload, fallbackMessage), {
    code: apiErrorCodeFromPayload(payload),
    detail,
    status: response.status,
    traceId,
  });
}

export function apiErrorFromXhr(xhr: XMLHttpRequest, fallbackMessage = "请求失败，请稍后重试。"): ApiRequestError {
  const payload = (() => {
    try {
      return JSON.parse(xhr.responseText);
    } catch {
      return null;
    }
  })();
  const detail = isRecord(payload) ? payload.detail : null;
  const traceId =
    (isRecord(payload) && typeof payload.trace_id === "string" ? payload.trace_id : "") ||
    xhr.getResponseHeader("x-trace-id") ||
    "";

  const error = new ApiRequestError(apiErrorMessageFromPayload(payload, fallbackMessage), {
    code: apiErrorCodeFromPayload(payload),
    detail,
    status: xhr.status,
    traceId,
  });
  if (isAuthRequiredError(error)) {
    redirectToLoginAfterAuthExpired();
  }
  return error;
}

function isAuthRequiredError(error: ApiRequestError) {
  return error.status === 401 && error.code === "AUTH_REQUIRED";
}

function redirectToLoginAfterAuthExpired() {
  if (typeof window === "undefined") {
    return;
  }

  const { pathname, search } = window.location;
  if (pathname.startsWith("/auth/")) {
    return;
  }

  useAuthStore.getState().logout();
  window.location.assign(`/auth/v1/login?next=${encodeURIComponent(`${pathname}${search}`)}`);
}

function throwApiError(response: Response, payload: unknown): never {
  const error = apiErrorFromResponse(response, payload);
  if (isAuthRequiredError(error)) {
    redirectToLoginAfterAuthExpired();
  }
  throw error;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let { hasHydrated, token } = useAuthStore.getState();

  if (!hasHydrated) {
    useAuthStore.getState().hydrate();
    ({ hasHydrated, token } = useAuthStore.getState());
  }

  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throwApiError(response, payload);
  }

  if (response.status === 204 || payload === null) {
    return undefined as T;
  }

  return (payload as ApiEnvelope<T>).data;
}

export function apiAuthHeaders(): Headers {
  let { hasHydrated, token } = useAuthStore.getState();

  if (!hasHydrated) {
    useAuthStore.getState().hydrate();
    ({ token } = useAuthStore.getState());
  }

  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

export async function apiBlobRequest(path: string, options: RequestInit = {}): Promise<Blob> {
  let { hasHydrated, token } = useAuthStore.getState();

  if (!hasHydrated) {
    useAuthStore.getState().hydrate();
    ({ hasHydrated, token } = useAuthStore.getState());
  }

  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throwApiError(response, payload);
  }

  return response.blob();
}

export type ApiAutomationEndpoint = {
  id: string;
  project_id: string;
  document_id: string | null;
  method: string;
  path: string;
  normalized_path: string;
  summary: string;
  description: string;
  tags: string[];
  parameters: Record<string, unknown>[];
  request_body: Record<string, unknown>;
  responses: Record<string, unknown>;
  auth: Record<string, unknown>;
  source: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ApiAutomationDocument = {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  source_url: string;
  file_path: string;
  version: string;
  status: string;
  endpoint_count: number;
  error_message: string;
  created_at: string;
};

export type ApiAutomationEnvironment = {
  id: string;
  project_id: string;
  name: string;
  api_base_url: string;
  username: string;
  auth_type: string;
  auth_config: Record<string, unknown>;
  variables: Record<string, unknown>;
  default_headers: Record<string, unknown>;
  timeout_seconds: number;
  verify_ssl: boolean;
  auth_state_ttl_seconds: number;
  description: string;
  created_at: string;
  updated_at: string;
};

export type ApiAutomationDebugPayload = {
  api_environment_id?: string | null;
  path_params?: Record<string, unknown>;
  query_params?: Record<string, unknown>;
  headers?: Record<string, unknown>;
  body?: unknown;
};

export type ApiAutomationDebugResult = {
  request: Record<string, unknown>;
  status_code: number;
  elapsed_ms: number;
  headers: Record<string, string>;
  body_text: string;
  body_json: unknown;
  error_message: string;
};

export type ApiAutomationGenerationRun = {
  id: string;
  project_id: string;
  api_environment_id: string | null;
  task_id: string;
  status: string;
  endpoint_ids: string[];
  source_test_case_ids: string[];
  generation_goal: string;
  options: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  error_message: string;
  created_at: string;
  finished_at: string | null;
  test_cases?: ApiAutomationTestCase[];
};

export type ApiAutomationTestCase = {
  id: string;
  project_id: string;
  endpoint_id: string | null;
  title: string;
  test_description: string;
  priority: string;
  coverage: string;
  preconditions: string[];
  request: Record<string, unknown>;
  test_data: Record<string, unknown>;
  assertions: Record<string, unknown>[];
  notes: string;
  created_at: string;
  updated_at: string;
};

export type ApiAutomationScript = {
  id: string;
  project_id: string;
  endpoint_id: string | null;
  name: string;
  status: string;
  suite_path: string;
  test_file_path: string;
  data_file_path: string;
  case_count: number;
  manual_modified: boolean;
  last_run_status: string;
  last_run_at: string | null;
  method: string;
  path: string;
  endpoint_summary: string;
  change?: "created" | "updated" | "unchanged";
  content?: string;
};

export type ApiAutomationRun = {
  id: string;
  project_id: string;
  api_environment_id: string | null;
  status: string;
  script_ids: string[];
  target_type: "scripts" | "scenario";
  target_ids: string[];
  execution_snapshot: {
    environment?: { id: string; name: string; api_base_url: string } | null;
    scenario?: { id: string; name: string; revision: number; step_count: number; published_hash: string };
    scripts?: Array<{
      id: string;
      endpoint_id?: string | null;
      name: string;
      case_count: number;
      method?: string;
      path?: string;
      endpoint_summary?: string;
    }>;
    script_count?: number;
    endpoint_count?: number;
    case_count?: number;
    suite_path?: string;
    test_file_path?: string;
    data_file_path?: string;
  };
  command_summary: string;
  stdout_path: string;
  stderr_path: string;
  json_report_path: string;
  scenario_result_path: string;
  summary: Record<string, unknown>;
  error_message: string;
  created_at: string;
  finished_at: string | null;
};

export type ApiRepairIssue = {
  failure_ids: string[];
  classification: string;
  confidence: number;
  root_cause: string;
  recommendation: string;
  repairable: boolean;
};

export type ApiRepairProposal = {
  target: "test_script";
  action: string;
  title: string;
  summary: string;
  confidence: number;
  proposed_changes: string[];
  case_updates?: Array<{
    case_id: string;
    expected_status_code: number;
    actual_status_code: number;
  }>;
  script_repair_allowed: boolean;
};

export type ApiRepairAttempt = {
  id: string;
  session_id: string;
  attempt_number: number;
  base_run_id: string;
  base_revision: number;
  status: string;
  user_context: string;
  diagnosis: { summary?: string; issues?: ApiRepairIssue[]; proposal?: ApiRepairProposal };
  validation: {
    summary?: Record<string, number>;
    changed_files?: string[];
    status?: string;
  };
  decision: string;
  applied_run_id: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

export type ApiRepairSession = {
  id: string;
  project_id: string;
  source_run_id: string;
  current_run_id: string;
  status: string;
  current_revision: number;
  attempts: ApiRepairAttempt[];
  available_actions: string[];
};

export type ApiAutomationScenarioStepType = "api_request" | "condition" | "wait" | "poll" | "assign";

export type ApiAutomationScenarioBinding = {
  target: string;
  source: {
    type: "literal" | "environment" | "scenario" | "step_output";
    value?: unknown;
    name?: string;
    step_id?: string;
    variable?: string;
  };
};

export type ApiScenarioAiPlanBinding = {
  target: {
    location: "path" | "query" | "header" | "cookie" | "json_body" | "form" | "multipart" | "raw_body";
    path: string;
  };
  source: {
    type: "literal" | "user_input" | "environment" | "secret" | "scenario" | "step_output" | "generated";
    value?: unknown;
    name?: string;
    key?: string;
    generator?: string;
    step_id?: string;
    variable?: string;
  };
  required?: boolean;
  transform?: "string" | "integer" | "number" | "boolean" | "json_encode" | "url_encode" | null;
};

export type ApiAutomationScenarioExtractor = {
  name: string;
  source?: "response.body" | "response.header" | "response.status";
  expression?: string;
  path?: string;
  required?: boolean;
};

export type ApiAutomationScenarioAssertion = {
  type: string;
  path?: string;
  expected?: unknown;
};

export type ApiAutomationScenarioAssetChange = {
  step_id: string;
  endpoint_id: string;
  change_type: "modified" | "missing";
  fields: string[];
};

export type ApiAutomationScenarioStep = {
  id: string;
  scenario_id: string;
  project_id: string;
  step_type: ApiAutomationScenarioStepType;
  endpoint_id: string | null;
  api_test_case_id: string | null;
  step_order: number;
  name: string;
  request_overrides: Record<string, unknown>;
  bindings: ApiAutomationScenarioBinding[];
  extractors: ApiAutomationScenarioExtractor[];
  assertions: ApiAutomationScenarioAssertion[];
  control_config: Record<string, unknown>;
  on_failure: "stop" | "continue" | "always_run";
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiAutomationScenarioStepInput = Pick<
  ApiAutomationScenarioStep,
  | "id"
  | "step_type"
  | "api_test_case_id"
  | "endpoint_id"
  | "step_order"
  | "name"
  | "request_overrides"
  | "bindings"
  | "extractors"
  | "assertions"
  | "control_config"
  | "on_failure"
  | "enabled"
>;

export type ApiAutomationScenario = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  status: "draft" | "ready" | "archived";
  variables: Record<string, unknown>;
  revision: number;
  published_hash: string;
  asset_changes: ApiAutomationScenarioAssetChange[];
  steps: ApiAutomationScenarioStep[];
  created_at: string;
  updated_at: string;
};

export type ApiAutomationScenarioValidation = {
  valid: boolean;
  errors: string[];
  warnings: string[];
};

export type ApiScenarioAiPlanNode = Omit<Partial<ApiAutomationScenarioStep>, "bindings"> & {
  id: string;
  type: ApiAutomationScenarioStepType;
  endpoint_id: string | null;
  bindings?: ApiScenarioAiPlanBinding[];
};

export type ApiScenarioAiPlanAccepted = {
  plan_id: string;
  scenario_id: string | null;
  lifecycle_status: "generating" | "completed" | "failed" | "expired";
};
export type ApiScenarioAiPlanResponse = ApiScenarioAiPlan | ApiScenarioAiPlanAccepted;
export type ApiScenarioAiPlan = {
  plan_id: string;
  plan_version: number;
  status: "preview" | "applied" | "discarded" | "expired";
  compiler_version: number;
  asset_fingerprint: string;
  environment_schema: Record<string, unknown>;
  graph_version: number;
  scenario_name: string;
  description: string;
  inputs: Array<{
    name: string;
    label: string;
    value_type: string;
    required: boolean;
    sensitive: boolean;
    description: string;
  }>;
  nodes: ApiScenarioAiPlanNode[];
  edges: Array<{ source: string; target: string; condition: string }>;
  assumptions: string[];
  warnings: string[];
  unresolved_items: string[];
  confidence: number;
  validation: ApiAutomationScenarioValidation;
  expected_revision: number | null;
  expires_at: string;
};

export type ApiAutomationScenarioRevision = {
  revision: number;
  published_hash: string;
  created_by: string;
  created_at: string;
  step_count: number;
};

export type ApiAutomationScenarioStepResult = {
  step_id: string;
  name: string;
  step_type: ApiAutomationScenarioStepType;
  status: "pending" | "passed" | "failed" | "skipped";
  duration_ms: number;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  assertions: Array<Record<string, unknown>>;
  attempts: Array<Record<string, unknown>>;
  error: string;
  skip_reason: string;
};

export type ApiAutomationScenarioRunResult = {
  scenario_id: string;
  status: "passed" | "failed";
  started_at: string;
  finished_at: string;
  duration_ms: number;
  steps: ApiAutomationScenarioStepResult[];
};

export type ApiAutomationRunList = {
  items: ApiAutomationRun[];
  total: number;
  page: number;
  page_size: number;
};

export type PerformanceRequestConfig = {
  path_parameters: Record<string, unknown>;
  query_parameters: Record<string, unknown>;
  headers: Record<string, unknown>;
  body: unknown;
  random_seed: number | null;
  transport: "http" | "sse";
  sse: PerformanceSseConfig | null;
};

export type PerformanceSseMatch = {
  event_name: string;
  source: "data_json" | "data_text" | "event_name";
  path: string;
  operator: "exists" | "non_empty" | "equals" | "contains" | "matches";
  expected?: unknown;
};

export type PerformanceSseMetric = {
  id: string;
  name: string;
  match: PerformanceSseMatch;
  occurrence: "first";
  missing_policy: "record_null" | "fail_request" | "ignore";
};

export type PerformanceSseConfig = {
  max_stream_seconds: number;
  end_rule: PerformanceSseMatch | null;
  metrics: PerformanceSseMetric[];
};

export type PerformanceLoadConfig = {
  mode: "fixed" | "gradient" | "stress" | "spike" | "endurance";
  users: number;
  spawn_rate: number;
  measurement_duration_seconds: number;
  wait_time_min_seconds: number;
  wait_time_max_seconds: number;
  request_timeout_seconds: number;
  stages: PerformanceLoadStage[];
};

export type PerformanceLoadStage = {
  name: string;
  target_users: number;
  spawn_rate: number;
  hold_seconds: number;
  order: number;
};

export type PerformanceDataConfig = {
  source: "fixed" | "json" | "csv";
  selection_strategy: "sequential_loop" | "random";
  json_rows: Array<Record<string, unknown>>;
  csv_file_name: string;
  csv_file_path: string;
};

export type PerformanceCircuitBreaker = {
  enabled: boolean;
  window_seconds: number;
  max_fail_ratio: number;
  consecutive_windows: number;
};

export type PerformanceGoal = {
  max_fail_ratio?: number;
  max_average_response_time_ms?: number;
  max_p95_response_time_ms?: number;
  min_average_rps?: number;
};

export type PerformanceSuccessRule = {
  kind: "status_code" | "jsonpath_exists" | "jsonpath_equals";
  status_codes?: number[];
  json_path?: string;
  expected?: unknown;
};

export type PerformanceTest = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  target_type: "endpoint";
  endpoint_id: string | null;
  endpoint_name: string;
  endpoint_method: string;
  endpoint_path: string;
  api_environment_id: string | null;
  environment_name: string;
  latest_script_id: string | null;
  request_config: PerformanceRequestConfig;
  load_config: PerformanceLoadConfig;
  data_config: PerformanceDataConfig;
  circuit_breaker: PerformanceCircuitBreaker;
  performance_goal: PerformanceGoal;
  success_rules: PerformanceSuccessRule[];
  latest_run_status: string;
  latest_goal_status: string;
  latest_run_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type PerformanceRequestPreview = {
  endpoint: { id: string; method: string; path: string; name: string };
  request_config: PerformanceRequestConfig;
  success_rules: PerformanceSuccessRule[];
  provenance: Record<string, string>;
  warnings: string[];
};

export type PerformanceTestCreatePayload = {
  name: string;
  description: string;
  target_type: "endpoint";
  endpoint_id: string;
  api_environment_id: string;
  request_config: PerformanceRequestConfig;
  load_config: PerformanceLoadConfig;
  data_config: PerformanceDataConfig;
  circuit_breaker: PerformanceCircuitBreaker;
  performance_goal: PerformanceGoal;
  success_rules?: PerformanceSuccessRule[];
};

export type PerformanceScript = {
  id: string;
  performance_test_id: string;
  project_id: string;
  generation_source: "ai_plan" | "default_plan" | "user_edited";
  model_id: string;
  prompt_version: string;
  plan: {
    schema_version: "v1";
    test_id: string;
    random_seed: number | null;
    request: Record<string, unknown>;
    load: Record<string, unknown>;
    data: Record<string, unknown>;
    success_rules: PerformanceSuccessRule[];
  };
  code: string;
  assumptions: unknown[];
  required_runtime_variables: string[];
  validation_status: "generating" | "validation_failed" | "valid";
  validation_result: { valid?: boolean; errors?: string[]; warnings?: string[]; code_hash?: string };
  created_at: string;
  updated_at: string;
  runtime_preview?: {
    request: { method: string; path: string; name: string; headers: Record<string, unknown>; body: unknown };
    success_rules: PerformanceSuccessRule[];
    env_headers: Record<string, string>;
    plan_headers: Record<string, unknown>;
    managed_header_names: string[];
  } | null;
};

export type PerformanceRun = {
  id: string;
  project_id: string;
  performance_test_id: string;
  script_id: string;
  status: "created" | "starting" | "ready" | "running" | "stopping" | "completed" | "stopped" | "failed" | "cancelled";
  load_config: Record<string, unknown>;
  target_host: string;
  latest_summary: Record<string, unknown>;
  error_code: string;
  error_message: string;
  trace_id: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
};

export type PerformanceRunHistory = {
  performance_test_id: string;
  retention_limit: number;
  runs: PerformanceRun[];
};

export type ApiScriptGenerationRun = {
  id: string;
  project_id: string;
  task_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  endpoint_ids: string[];
  api_environment_id: string | null;
  force: boolean;
  suite_path: string;
  changed_files: string[];
  summary: { created?: number; updated?: number; unchanged?: number };
  error_message: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type PerformanceRunReport = { name: string; size: number };

export type PerformanceRunReports = { run_id: string; reports: PerformanceRunReport[] };

export type ReportCenterItem = {
  id: string;
  report_type: "performance";
  project_id: string;
  project_name: string;
  test_id: string;
  test_name: string;
  run_id: string;
  analysis_id: string;
  analysis_version: number;
  name: string;
  status: "collecting" | "analyzing" | "completed" | "failed";
  verdict: "pass" | "conditional_pass" | "fail" | "indeterminate";
  quality_status: "complete" | "partial" | "invalid";
  error_message: string;
  created_at: string;
  updated_at: string;
  href: string;
};

export type PerformanceRunFailure = {
  request_name: string;
  method: string;
  reason: string;
  count: number;
  sample_status_code: number | null;
};

export type PerformanceRunException = {
  request_name: string;
  exception_type: string;
  message: string;
  count: number;
};

export type PerformanceRunStats = {
  run: PerformanceRun;
  stats: Array<Record<string, unknown>>;
  request_stats: Array<Record<string, unknown>>;
  failures: PerformanceRunFailure[];
  exceptions: PerformanceRunException[];
  events: Array<Record<string, unknown>>;
  sse_metrics: {
    attempt_count: number;
    metrics: Array<{
      metric_id: string;
      attempt_count: number;
      matched_count: number;
      missing_count: number;
      failure_count: number;
      average_ms: number | null;
      p50_ms: number | null;
      p95_ms: number | null;
      p99_ms: number | null;
    }>;
  };
};

export type PerformanceRunCharts = {
  run_id: string;
  samples: Array<Record<string, unknown>>;
};

export type PerformanceAnalysisEvidence = {
  source: string;
  level: "observed" | "derived" | "inferred";
  title: string;
  detail: string;
  reference?: string;
};

export type PerformanceAnalysisChange = {
  id: string;
  target_type: "performance_config" | "locust_script" | "platform_code";
  target: string;
  before?: unknown;
  after?: unknown;
  reason: string;
  risk_level: "low" | "medium" | "high";
};

export type PerformanceMetricObjective = {
  evidence_id: string;
  metric: string;
  operator: "lte" | "gte";
  target: number;
  actual: number | null;
  status: "passed" | "failed" | "not_evaluated";
};

export type PerformanceMetricSnapshot = {
  schema_version?: number;
  calculator_version?: string;
  run_id?: string;
  source_fingerprint?: string;
  verdict?: "pass" | "conditional_pass" | "fail" | "indeterminate";
  quality?: {
    status?: "complete" | "partial" | "invalid";
    coverage?: number;
    issues?: string[];
    diagnostic_missing_evidence?: string[];
    sample_count?: number;
    termination_reason?: string;
    termination_label?: string;
    actual_duration_seconds?: number | null;
    configured_duration_seconds?: number | null;
    duration_complete?: boolean | null;
  };
  aggregate?: {
    request_count?: number;
    failure_count?: number;
    failure_rate?: number;
    requests_per_second?: number;
    average_response_time_ms?: number;
    p50_response_time_ms?: number | null;
    p95_response_time_ms?: number | null;
    p99_response_time_ms?: number | null;
  };
  capacity?: {
    observed_peak_throughput?: number;
    stable_throughput?: number | null;
    knee_point?: number | null;
    knee_point_reason?: string;
  };
  test_validity?: {
    status?: "complete" | "partial" | "invalid";
    issues?: string[];
    sample_count?: number;
    coverage?: number;
    termination_reason?: string;
  };
  stage_analysis?: Array<{
    name: string;
    target_users: number;
    actual_users?: number;
    sample_count?: number;
    requests_per_second?: number;
    p95_response_time_ms?: number | null;
    failure_rate?: number;
    status?: string;
  }>;
  latency_analysis?: Record<string, number | null>;
  capacity_analysis?: {
    observed_stable_capacity?: {
      users?: number;
      requests_per_second?: number;
      p95_response_time_ms?: number | null;
    } | null;
    knee_point?: { between_users?: number[]; reason?: string } | null;
    can_claim_stable_capacity?: boolean;
    reason?: string;
    sample_count?: number;
  };
  failure_analysis?: Array<{ kind: string; count: number; ratio: number; example?: string }>;
  objectives?: PerformanceMetricObjective[];
  series?: Array<Record<string, unknown>>;
  evidence_index?: Array<Record<string, unknown>>;
};

export type PerformanceReportFinding = {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  level?: "observed" | "derived" | "inferred";
  title: string;
  statement: string;
  confidence: number;
  evidence_refs: string[];
  alternative_hypotheses?: string[];
  missing_evidence?: string[];
};

export type PerformanceReportSnapshot = {
  schema_version?: number;
  verdict?: "pass" | "conditional_pass" | "fail" | "indeterminate";
  verdict_reasons?: string[];
  executive_summary?: string;
  capacity_summary?: string;
  findings?: PerformanceReportFinding[];
  recommendations?: Array<{
    id: string;
    priority: string;
    action: string;
    expected_effect?: string;
    cost?: string;
    verification?: string;
    acceptance_criteria?: string[];
    finding_refs?: string[];
    proposed_change_id?: string;
  }>;
  diagnosis_evidence?: Array<PerformanceAnalysisEvidence & { evidence_id: string }>;
};

export type PerformanceAnalysis = {
  id: string;
  project_id: string;
  run_id: string;
  status: "collecting" | "analyzing" | "waiting_approval" | "failed" | "rejected";
  legacy_status: string;
  analysis_status: "collecting" | "analyzing" | "completed" | "failed";
  analysis_stage: string;
  repair_status: "not_applicable" | "available" | "rejected" | "preflighting" | "rerunning" | "completed";
  analysis_version: number;
  category: string;
  summary: string;
  direct_cause: string;
  root_cause: string;
  confidence: number;
  evidence: PerformanceAnalysisEvidence[];
  missing_evidence: string[];
  proposal: {
    changes?: PerformanceAnalysisChange[];
    requires_second_approval?: boolean;
    can_auto_rerun?: boolean;
    readonly?: boolean;
  };
  metric_snapshot: PerformanceMetricSnapshot;
  report_snapshot: PerformanceReportSnapshot;
  calculator_version: string;
  prompt_version: string;
  source_fingerprint: string;
  audience: "engineer" | "technical_manager" | "business_owner";
  model_name: string;
  error_message: string;
  created_by: string;
  created_at: string;
  finished_at?: string | null;
  updated_at: string;
  available_actions: string[];
  application_status:
    | "not_requested"
    | "preflighting"
    | "preflight_failed"
    | "rerunning"
    | "completed"
    | "apply_failed"
    | "superseded";
  applicable_change_ids: string[];
  selected_change_ids: string[];
  preflight: {
    passed?: boolean;
    status_code?: number | null;
    final_url?: string;
    failures?: string[];
    response?: Record<string, unknown>;
  };
  applied_script_id: string;
  applied_run_id: string;
  applied_by: string;
  applied_at?: string | null;
};

export type PerformanceRunStartPayload = {
  users: number;
  spawn_rate: number;
  run_time: number;
  host?: string;
};

export type PerformanceScenario = {
  id: string;
  project_id: string;
  name: string;
  description: string;
  api_environment_id: string;
  definition_version: number;
  scenario_definition: Record<string, unknown>;
  load_profile: Record<string, unknown>;
  data_source: Record<string, unknown>;
  quality_gate: Record<string, unknown>;
  safety_policy: Record<string, unknown>;
};

export type PerformanceScenarioCreatePayload = {
  name: string;
  description: string;
  api_environment_id: string;
  scenario_definition: Record<string, unknown>;
  load_profile: Record<string, unknown>;
  data_source: Record<string, unknown>;
  quality_gate: Record<string, unknown>;
  safety_policy: Record<string, unknown>;
};

export type ApiAutomationCaseSet = {
  id: string;
  project_id: string;
  name: string;
  notes: string;
  status: string;
  endpoint_count: number;
  case_count: number;
  latest_generation_run_id: string | null;
  created_at: string;
  updated_at: string;
};

export function listApiAutomationEndpoints(projectId: string) {
  return apiRequest<ApiAutomationEndpoint[]>(`/projects/${projectId}/api-endpoints`);
}

export function previewPerformanceRequest(
  projectId: string,
  payload: { endpoint_id: string; api_environment_id?: string },
) {
  return apiRequest<PerformanceRequestPreview>(`/projects/${projectId}/performance-tests/request-preview`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPerformanceTests(projectId: string) {
  return apiRequest<PerformanceTest[]>(`/projects/${projectId}/performance-tests`);
}

export function getPerformanceTest(projectId: string, testId: string) {
  return apiRequest<PerformanceTest>(`/projects/${projectId}/performance-tests/${testId}`);
}

export function createPerformanceTest(projectId: string, payload: PerformanceTestCreatePayload) {
  return apiRequest<PerformanceTest>(`/projects/${projectId}/performance-tests`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createPerformanceScenario(projectId: string, payload: PerformanceScenarioCreatePayload) {
  return apiRequest<PerformanceScenario>(`/projects/${projectId}/performance-scenarios`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePerformanceTest(
  projectId: string,
  testId: string,
  payload: Partial<PerformanceTestCreatePayload>,
) {
  return apiRequest<PerformanceTest>(`/projects/${projectId}/performance-tests/${testId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deletePerformanceTest(projectId: string, testId: string) {
  return apiRequest<void>(`/projects/${projectId}/performance-tests/${testId}`, { method: "DELETE" });
}

export function generatePerformanceScript(projectId: string, testId: string) {
  return apiRequest<PerformanceScript>(`/projects/${projectId}/performance-tests/${testId}/scripts/generate`, {
    method: "POST",
  });
}

export function getPerformanceScript(projectId: string, testId: string) {
  return apiRequest<PerformanceScript>(`/projects/${projectId}/performance-tests/${testId}/script`);
}

export function updatePerformanceScriptConfiguration(
  projectId: string,
  testId: string,
  scriptId: string,
  payload: {
    request?: Record<string, unknown>;
    load?: Record<string, unknown>;
    success_rules?: PerformanceSuccessRule[];
  },
) {
  return apiRequest<PerformanceScript>(
    `/projects/${projectId}/performance-tests/${testId}/scripts/${scriptId}/configuration`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}

export function createPerformanceRun(projectId: string, testId: string, scriptId: string) {
  return apiRequest<{ id: string; status: string }>(`/projects/${projectId}/performance-tests/${testId}/runs`, {
    method: "POST",
    body: JSON.stringify({ script_id: scriptId }),
  });
}

export function getPerformanceRun(projectId: string, runId: string) {
  return apiRequest<PerformanceRun>(`/projects/${projectId}/performance-test-runs/${runId}`);
}

export function deletePerformanceRun(projectId: string, runId: string) {
  return apiRequest<void>(`/projects/${projectId}/performance-test-runs/${runId}`, { method: "DELETE" });
}

export function listPerformanceRunHistory(projectId: string, testId: string) {
  return apiRequest<PerformanceRunHistory>(`/projects/${projectId}/performance-tests/${testId}/runs/history`);
}

export function getPerformanceRunStats(projectId: string, runId: string) {
  return apiRequest<PerformanceRunStats>(`/projects/${projectId}/performance-test-runs/${runId}/stats`);
}

export function getPerformanceRunCharts(projectId: string, runId: string) {
  return apiRequest<PerformanceRunCharts>(`/projects/${projectId}/performance-test-runs/${runId}/charts`);
}

export function createPerformanceAnalysis(projectId: string, runId: string) {
  return apiRequest<PerformanceAnalysis>(`/projects/${projectId}/performance-test-runs/${runId}/ai-analysis`, {
    method: "POST",
  });
}

export function listPerformanceRunAnalyses(projectId: string, runId: string) {
  return apiRequest<PerformanceAnalysis[]>(`/projects/${projectId}/performance-test-runs/${runId}/ai-analysis`);
}

export function getPerformanceAnalysis(projectId: string, analysisId: string) {
  return apiRequest<PerformanceAnalysis>(`/projects/${projectId}/performance-analysis/${analysisId}`);
}

export function rejectPerformanceAnalysis(projectId: string, analysisId: string) {
  return apiRequest<PerformanceAnalysis>(`/projects/${projectId}/performance-analysis/${analysisId}/reject`, {
    method: "POST",
  });
}

export function applyPerformanceAnalysis(projectId: string, analysisId: string, changeIds: string[]) {
  return apiRequest<PerformanceAnalysis>(`/projects/${projectId}/performance-analysis/${analysisId}/apply-and-rerun`, {
    method: "POST",
    body: JSON.stringify({ change_ids: changeIds }),
  });
}

export function startPerformanceRun(
  projectId: string,
  testId: string,
  runId: string,
  payload: PerformanceRunStartPayload,
) {
  return apiRequest<{ id: string; accepted: boolean }>(
    `/projects/${projectId}/performance-tests/${testId}/runs/${runId}/start`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function listPerformanceRunReports(projectId: string, runId: string) {
  return apiRequest<PerformanceRunReports>(`/projects/${projectId}/performance-test-runs/${runId}/reports`);
}

export function listReportCenterItems(projectId = "all", reportType = "performance") {
  const params = new URLSearchParams({ project_id: projectId, report_type: reportType });
  return apiRequest<ReportCenterItem[]>(`/reports?${params.toString()}`);
}

export function deleteReportCenterItem(reportId: string, reportType = "performance") {
  const params = new URLSearchParams({ report_type: reportType });
  return apiRequest<void>(`/reports/${reportId}?${params.toString()}`, { method: "DELETE" });
}

export function downloadPerformanceRunReport(projectId: string, runId: string, filename: string) {
  return apiBlobRequest(
    `/projects/${projectId}/performance-test-runs/${runId}/reports/${encodeURIComponent(filename)}`,
  );
}

export async function streamPerformanceRun(
  projectId: string,
  runId: string,
  signal: AbortSignal,
  onEvent: (event: string, payload: Record<string, unknown>) => void,
) {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/performance-test-runs/${runId}/stream`, {
    credentials: "include",
    headers: { ...Object.fromEntries(apiAuthHeaders()), Accept: "text/event-stream" },
    signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throwApiError(response, payload);
  }
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? "";
    for (const message of messages) {
      const event = message.match(/^event: (.+)$/m)?.[1];
      const data = message.match(/^data: (.+)$/m)?.[1];
      if (event && data) onEvent(event, JSON.parse(data) as Record<string, unknown>);
    }
  }
}

export function stopPerformanceRun(projectId: string, runId: string) {
  return apiRequest<{ id: string; accepted: boolean }>(`/projects/${projectId}/performance-test-runs/${runId}/stop`, {
    method: "POST",
  });
}

export function resetPerformanceRunStats(projectId: string, runId: string) {
  return apiRequest<{ id: string; reset: boolean }>(
    `/projects/${projectId}/performance-test-runs/${runId}/reset-stats`,
    {
      method: "POST",
    },
  );
}

export function deleteApiAutomationEndpoint(projectId: string, endpointId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-endpoints/${endpointId}`, {
    method: "DELETE",
  });
}

export function debugApiAutomationEndpoint(
  projectId: string,
  endpointId: string,
  payload: ApiAutomationDebugPayload,
  files: Record<string, File | null> = {},
) {
  const selectedFiles = Object.entries(files).filter((entry): entry is [string, File] => entry[1] instanceof File);
  if (selectedFiles.length > 0) {
    const formData = new FormData();
    formData.append("payload", JSON.stringify(payload));
    for (const [fieldName, file] of selectedFiles) {
      formData.append(`file::${fieldName}`, file, file.name);
    }
    return apiRequest<ApiAutomationDebugResult>(`/projects/${projectId}/api-endpoints/${endpointId}/debug`, {
      method: "POST",
      body: formData,
    });
  }
  return apiRequest<ApiAutomationDebugResult>(`/projects/${projectId}/api-endpoints/${endpointId}/debug`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importOpenApiDocument(
  projectId: string,
  payload: { source_type: "file" | "url"; content?: string; url?: string; name?: string },
) {
  return apiRequest<ApiAutomationDocument>(`/projects/${projectId}/api-documents/import`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listApiAutomationEnvironments(projectId: string) {
  return apiRequest<ApiAutomationEnvironment[]>(`/projects/${projectId}/api-environments`);
}

export function createApiAutomationEnvironment(projectId: string, payload: Record<string, unknown>) {
  return apiRequest<ApiAutomationEnvironment>(`/projects/${projectId}/api-environments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateApiAutomationEnvironment(
  projectId: string,
  environmentId: string,
  payload: Record<string, unknown>,
) {
  return apiRequest<ApiAutomationEnvironment>(`/projects/${projectId}/api-environments/${environmentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteApiAutomationEnvironment(projectId: string, environmentId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-environments/${environmentId}`, {
    method: "DELETE",
  });
}

export function generateApiAutomationTestCases(projectId: string, payload: Record<string, unknown>) {
  return apiRequest<ApiAutomationGenerationRun>(`/projects/${projectId}/api-test-cases/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listApiAutomationTestCases(projectId: string, params?: { endpoint_id?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.endpoint_id) searchParams.set("endpoint_id", params.endpoint_id);
  const query = searchParams.toString();
  return apiRequest<ApiAutomationTestCase[]>(`/projects/${projectId}/api-test-cases${query ? `?${query}` : ""}`);
}

export function getApiAutomationTestCase(projectId: string, caseId: string) {
  return apiRequest<ApiAutomationTestCase>(`/projects/${projectId}/api-test-cases/${caseId}`);
}

export function deleteApiAutomationTestCase(projectId: string, caseId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-test-cases/${caseId}`, {
    method: "DELETE",
  });
}

export function listApiAutomationGenerationRuns(projectId: string) {
  return apiRequest<ApiAutomationGenerationRun[]>(`/projects/${projectId}/api-automation/generation-runs`);
}

export function listApiAutomationCaseSets(projectId: string) {
  return apiRequest<ApiAutomationCaseSet[]>(`/projects/${projectId}/api-case-sets`);
}

export function listUiAutomationAssets(projectId: string) {
  return apiRequest<UiAutomationAsset[]>(`/projects/${projectId}/ui-automation/assets`);
}

export function listUiAutomationGenerationRuns(projectId: string) {
  return apiRequest<UiAutomationGenerationRun[]>(`/projects/${projectId}/ui-automation/generation-runs`);
}

export function createUiAutomationGenerationRun(
  projectId: string,
  payload: { test_case_id: string; environment_id: string; exploration_run_id?: string },
) {
  return apiRequest<UiAutomationGenerationRun>(`/projects/${projectId}/ui-automation/generation-runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getUiAutomationGenerationRun(projectId: string, runId: string) {
  return apiRequest<UiAutomationGenerationRun>(`/projects/${projectId}/ui-automation/generation-runs/${runId}`);
}

export function listUiAutomationAssetGenerationRuns(projectId: string, assetId: string) {
  return apiRequest<UiAutomationGenerationRun[]>(
    `/projects/${projectId}/ui-automation/assets/${assetId}/generation-runs`,
  );
}

export function listUiAutomationAssetExecutionRuns(projectId: string, assetId: string) {
  return apiRequest<UiAutomationExecutionRun[]>(`/projects/${projectId}/ui-automation/assets/${assetId}/runs`);
}

export function getUiAutomationAsset(projectId: string, assetId: string) {
  return apiRequest<UiAutomationAsset>(`/projects/${projectId}/ui-automation/assets/${assetId}`);
}

export function getUiAutomationRunLogs(projectId: string, runId: string) {
  return apiRequest<UiAutomationRunLogs>(`/projects/${projectId}/ui-automation/runs/${runId}/logs`);
}

export function getUiAutomationLiveView(projectId: string, runId: string) {
  return apiRequest<UiAutomationLiveView>(`/projects/${projectId}/ui-automation/runs/${runId}/live-view`);
}

export function createUiAutomationExecutionRun(projectId: string, assetId: string, environmentId: string) {
  return apiRequest<UiAutomationExecutionRun>(`/projects/${projectId}/ui-automation/assets/${assetId}/runs`, {
    method: "POST",
    body: JSON.stringify({ environment_id: environmentId }),
  });
}

export function getUiAutomationExecutionRun(projectId: string, runId: string) {
  return apiRequest<UiAutomationExecutionRun>(`/projects/${projectId}/ui-automation/runs/${runId}`);
}

export function stopUiAutomationExecutionRun(projectId: string, runId: string) {
  return apiRequest<UiAutomationExecutionRun>(`/projects/${projectId}/ui-automation/runs/${runId}/stop`, {
    method: "POST",
  });
}

export function deleteUiAutomationExecutionRun(projectId: string, runId: string) {
  return apiRequest<void>(`/projects/${projectId}/ui-automation/runs/${runId}`, { method: "DELETE" });
}

export function createApiAutomationCaseSet(projectId: string, payload: { name: string; notes: string }) {
  return apiRequest<ApiAutomationCaseSet>(`/projects/${projectId}/api-case-sets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateApiAutomationCaseSet(projectId: string, setId: string, payload: { name: string; notes: string }) {
  return apiRequest<ApiAutomationCaseSet>(`/projects/${projectId}/api-case-sets/${setId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function getApiAutomationGenerationRun(projectId: string, runId: string) {
  return apiRequest<ApiAutomationGenerationRun>(`/projects/${projectId}/api-automation/generation-runs/${runId}`);
}

export function generateApiAutomationScripts(
  projectId: string,
  payload: { endpoint_ids: string[]; force?: boolean; api_environment_id?: string | null },
) {
  return apiRequest<ApiScriptGenerationRun>(`/projects/${projectId}/api-automation/scripts/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getApiScriptGenerationRun(projectId: string, runId: string) {
  return apiRequest<ApiScriptGenerationRun>(`/projects/${projectId}/api-automation/scripts/generation-runs/${runId}`);
}

export function listApiAutomationScripts(projectId: string) {
  return apiRequest<ApiAutomationScript[]>(`/projects/${projectId}/api-scripts`);
}

export function deleteApiAutomationScript(projectId: string, scriptId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-scripts/${scriptId}`, {
    method: "DELETE",
  });
}

export function createApiAutomationRun(
  projectId: string,
  payload: { script_ids: string[]; api_environment_id?: string | null },
) {
  return apiRequest<ApiAutomationRun>(`/projects/${projectId}/api-runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listApiAutomationRuns(
  projectId: string,
  params?: { page?: number; page_size?: number; status?: string; environment_id?: string; keyword?: string },
) {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.status) searchParams.set("status", params.status);
  if (params?.environment_id) searchParams.set("environment_id", params.environment_id);
  if (params?.keyword) searchParams.set("keyword", params.keyword);
  const query = searchParams.toString();
  return apiRequest<ApiAutomationRunList>(`/projects/${projectId}/api-runs${query ? `?${query}` : ""}`);
}

export function getApiAutomationRun(projectId: string, runId: string) {
  return apiRequest<ApiAutomationRun>(`/projects/${projectId}/api-runs/${runId}`);
}

export function deleteApiAutomationRun(projectId: string, runId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-runs/${runId}`, {
    method: "DELETE",
  });
}

export function getApiAutomationRunLogs(projectId: string, runId: string) {
  return apiRequest<{ stdout: string; stderr: string }>(`/projects/${projectId}/api-runs/${runId}/logs`);
}

export function getApiAutomationRunReport(projectId: string, runId: string) {
  return apiRequest<Record<string, unknown>>(`/projects/${projectId}/api-runs/${runId}/report`);
}

export function createApiRepairSession(projectId: string, runId: string, userContext = "") {
  return apiRequest<{ session_id: string; attempt_id: string; status: string }>(
    `/projects/${projectId}/api-runs/${runId}/repair-session`,
    { method: "POST", body: JSON.stringify({ user_context: userContext }) },
  );
}

export function getApiRepairSession(projectId: string, sessionId: string) {
  return apiRequest<ApiRepairSession>(`/projects/${projectId}/api-repair-sessions/${sessionId}`);
}

export function createApiRepairAttempt(projectId: string, sessionId: string, userContext = "") {
  return apiRequest<{ session_id: string; attempt_id: string; status: string }>(
    `/projects/${projectId}/api-repair-sessions/${sessionId}/attempts`,
    { method: "POST", body: JSON.stringify({ user_context: userContext }) },
  );
}

export function approveApiRepairAttempt(projectId: string, attemptId: string, comment = "") {
  return apiRequest<ApiRepairAttempt>(`/projects/${projectId}/api-repair-attempts/${attemptId}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function applyApiRepairAttempt(projectId: string, attemptId: string, comment = "") {
  return apiRequest<{ session_id: string; attempt_id: string; run_id: string; status: string }>(
    `/projects/${projectId}/api-repair-attempts/${attemptId}/apply`,
    { method: "POST", body: JSON.stringify({ comment }) },
  );
}

export function discardApiRepairAttempt(projectId: string, attemptId: string, comment = "") {
  return apiRequest<ApiRepairAttempt>(`/projects/${projectId}/api-repair-attempts/${attemptId}/discard`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function rejectApiRepairAttempt(projectId: string, attemptId: string, comment = "") {
  return apiRequest<ApiRepairAttempt>(`/projects/${projectId}/api-repair-attempts/${attemptId}/reject`, {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}

export function getApiRepairAttemptDiff(projectId: string, attemptId: string) {
  return apiRequest<{ diff: string }>(`/projects/${projectId}/api-repair-attempts/${attemptId}/diff`);
}

export function getApiAutomationScenarioRunResult(projectId: string, runId: string) {
  return apiRequest<ApiAutomationScenarioRunResult>(`/projects/${projectId}/api-runs/${runId}/scenario-result`);
}

export function listApiAutomationScenarios(projectId: string) {
  return apiRequest<ApiAutomationScenario[]>(`/projects/${projectId}/api-scenarios`);
}

export function createApiScenarioAiPlan(
  projectId: string,
  payload: {
    goal: string;
    source_scope?: { endpoint_ids?: string[]; tags?: string[] };
    constraints?: {
      environment_id?: string | null;
      require_cleanup?: boolean;
    };
    scenario_id?: string | null;
  },
) {
  return apiRequest<ApiScenarioAiPlanAccepted>(`/projects/${projectId}/api-scenarios/ai-plan`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function applyApiScenarioAiPlan(
  projectId: string,
  planId: string,
  payload: { scenario_id: string; expected_revision: number; confirmation: string },
) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios/ai-plans/${planId}/apply`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getApiScenarioAiPlan(projectId: string, planId: string) {
  return apiRequest<ApiScenarioAiPlanResponse>(`/projects/${projectId}/api-scenarios/ai-plans/${planId}`);
}

export function getApiAutomationScenario(projectId: string, scenarioId: string) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios/${scenarioId}`);
}

export function createApiAutomationScenario(
  projectId: string,
  payload: { name: string; description?: string; variables?: Record<string, unknown> },
) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateApiAutomationScenario(
  projectId: string,
  scenarioId: string,
  payload: { name: string; description?: string; variables?: Record<string, unknown> },
) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios/${scenarioId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteApiAutomationScenario(projectId: string, scenarioId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-scenarios/${scenarioId}`, { method: "DELETE" });
}

export function replaceApiAutomationScenarioSteps(
  projectId: string,
  scenarioId: string,
  steps: ApiAutomationScenarioStepInput[],
) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios/${scenarioId}/steps`, {
    method: "PUT",
    body: JSON.stringify({ steps }),
  });
}

export function validateApiAutomationScenario(projectId: string, scenarioId: string) {
  return apiRequest<ApiAutomationScenarioValidation>(`/projects/${projectId}/api-scenarios/${scenarioId}/validate`, {
    method: "POST",
  });
}

export function publishApiAutomationScenario(projectId: string, scenarioId: string, confirmAssetChanges = false) {
  return apiRequest<ApiAutomationScenario>(`/projects/${projectId}/api-scenarios/${scenarioId}/publish`, {
    method: "POST",
    body: JSON.stringify({ confirm_asset_changes: confirmAssetChanges }),
  });
}

export function listApiAutomationScenarioRevisions(projectId: string, scenarioId: string) {
  return apiRequest<ApiAutomationScenarioRevision[]>(`/projects/${projectId}/api-scenarios/${scenarioId}/revisions`);
}

export function restoreApiAutomationScenarioRevision(projectId: string, scenarioId: string, revision: number) {
  return apiRequest<ApiAutomationScenario>(
    `/projects/${projectId}/api-scenarios/${scenarioId}/revisions/${revision}/restore`,
    { method: "POST" },
  );
}

export function executeApiAutomationScenario(
  projectId: string,
  scenarioId: string,
  apiEnvironmentId: string,
  source: "published" | "draft" = "published",
) {
  return apiRequest<ApiAutomationRun>(`/projects/${projectId}/api-scenarios/${scenarioId}/execute`, {
    method: "POST",
    body: JSON.stringify({ api_environment_id: apiEnvironmentId, source }),
  });
}

export function roleToLabel(role: ApiRole) {
  return { admin: "管理员", tester: "测试工程师", guest: "访客" }[role];
}

export function labelToRole(label: string): ApiRole {
  return ({ 管理员: "admin", 测试工程师: "tester", 访客: "guest" } as Record<string, ApiRole>)[label] ?? "tester";
}

export function statusToLabel(status: ApiStatus) {
  return status === "enabled" ? "启用" : "禁用";
}

export function labelToStatus(label: string): ApiStatus {
  return label === "禁用" ? "disabled" : "enabled";
}

export function formatDateTime(value: string | null) {
  const timestamp = parseApiTimestamp(value);
  if (!Number.isFinite(timestamp)) {
    return "-";
  }

  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
    .formatToParts(new Date(timestamp))
    .reduce<Record<string, string>>((result, part) => {
      result[part.type] = part.value;
      return result;
    }, {});

  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

function parseApiTimestamp(value: string | null) {
  if (!value) {
    return Number.NaN;
  }
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized);
  return new Date(hasTimeZone ? normalized : `${normalized}Z`).getTime();
}

export function operationLogActionToLabel(action: string) {
  return (
    (
      {
        archive: "归档",
        archive_global_knowledge: "归档全局知识",
        answer_requirement_clarification: "答复澄清问题",
        api_error: "接口错误",
        assign_model: "分配模型",
        auto_auth_login: "自动登录",
        cancel: "取消",
        cancel_requirement_analysis: "取消需求分析",
        confirm: "确认",
        create: "新增",
        create_global_knowledge_version: "新增知识版本",
        delete: "删除",
        delete_conversation: "删除会话",
        export: "导出",
        fail_requirement_analysis: "需求分析失败",
        finalize_requirement_analysis: "确认最终需求",
        finish: "完成",
        finish_requirement_analysis: "完成需求分析",
        generate: "生成",
        interrupt_exploration: "中断探索",
        login: "登录",
        logout: "登出",
        publish: "发布",
        query: "查询",
        resolve_conflict: "解决冲突",
        restore: "恢复",
        retry: "重试",
        run: "执行",
        set_primary_file: "设置主文件",
        cleanup: "清理",
        client_error: "客户端错误",
        start: "开始",
        start_requirement_analysis: "开始需求分析",
        stop_stale_test_case_generation: "停止过期用例生成",
        submit_requirement_analysis: "提交需求分析",
        update: "编辑",
        update_global_knowledge: "编辑全局知识",
        update_retention_policy: "更新保留策略",
        upload: "上传",
        upload_global_knowledge: "上传全局知识",
      } as Record<string, string>
    )[action] ?? action
  );
}

export function operationLogResultToLabel(result: string) {
  return (
    (
      {
        cancelled: "已取消",
        failed: "失败",
        partial_success: "部分成功",
        success: "成功",
      } as Record<string, string>
    )[result] ?? result
  );
}

export function operationLogModuleToLabel(module: string) {
  return (
    (
      {
        agent: "智能体",
        api_automation: "接口自动化",
        auth: "登录认证",
        environment: "环境",
        exploration: "站点探索",
        frontend: "前端",
        knowledge: "知识库",
        model: "模型配置",
        operation_log: "系统日志",
        performance_testing: "性能测试",
        project: "项目",
        requirement: "需求",
        system_setting: "系统设置",
        test_case: "测试用例",
        task: "任务",
        user: "用户",
        api: "接口",
      } as Record<string, string>
    )[module] ?? module
  );
}

export function healthStatusToLabel(healthStatus: string) {
  return (
    (
      {
        unknown: "未测试",
        healthy: "通过",
        unhealthy: "失败",
        timeout: "超时",
        testing: "测试中",
      } as Record<string, string>
    )[healthStatus] ?? healthStatus
  );
}

export function generateTestPoints(projectId: string, documentId: string) {
  return apiRequest<ApiTestPointGenerationRun>(
    `/projects/${projectId}/requirements/${documentId}/test-points/generate`,
    { method: "POST" },
  );
}
