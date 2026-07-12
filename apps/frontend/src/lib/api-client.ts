"use client";

import { useAuthStore } from "@/stores/auth-store";

function normalizeApiBaseUrl(value: string) {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export const API_BASE_URL = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1");

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
  exploration_mode: "goal" | "autonomous";
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
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
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
  source: string;
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

export type ApiAutomationScriptFile = {
  key: string;
  name: string;
  kind: "test" | "data";
  language: "python" | "json";
  content: string;
};

export type ApiAutomationRun = {
  id: string;
  project_id: string;
  api_environment_id: string | null;
  status: string;
  script_ids: string[];
  command_summary: string;
  stdout_path: string;
  stderr_path: string;
  json_report_path: string;
  summary: Record<string, unknown>;
  error_message: string;
  created_at: string;
  finished_at: string | null;
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

export function deleteApiAutomationEndpoint(projectId: string, endpointId: string) {
  return apiRequest<void>(`/projects/${projectId}/api-endpoints/${endpointId}`, {
    method: "DELETE",
  });
}

export function debugApiAutomationEndpoint(projectId: string, endpointId: string, payload: ApiAutomationDebugPayload) {
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
  return apiRequest<{
    suite_id: string;
    suite_path: string;
    summary: { created: number; updated: number; unchanged: number };
    scripts: ApiAutomationScript[];
  }>(
    `/projects/${projectId}/api-automation/scripts/generate`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function listApiAutomationScripts(projectId: string) {
  return apiRequest<ApiAutomationScript[]>(`/projects/${projectId}/api-scripts`);
}

export function getApiAutomationScriptFiles(projectId: string, scriptId: string) {
  return apiRequest<{ script_id: string; files: ApiAutomationScriptFile[] }>(
    `/projects/${projectId}/api-scripts/${scriptId}/files`,
  );
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

export function getApiAutomationRun(projectId: string, runId: string) {
  return apiRequest<ApiAutomationRun>(`/projects/${projectId}/api-runs/${runId}`);
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
        auth: "登录认证",
        environment: "环境",
        exploration: "站点探索",
        frontend: "前端",
        knowledge: "知识库",
        model: "模型配置",
        operation_log: "系统日志",
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
