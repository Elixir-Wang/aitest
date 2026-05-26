"use client";

import { useAuthStore } from "@/stores/auth-store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type ApiEnvelope<T> = {
  data: T;
  trace_id: string;
};

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
  created_by: string;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

export type ApiAgentModelAssignment = {
  agent_id: string;
  agent_name: string;
  agent_description: string;
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

export type ApiDashboardMetric = {
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

export type ApiAvailableAction = {
  key: string;
  label: string;
  enabled: boolean;
  disabled_reason: string;
  risk_level: "normal" | "warning" | "danger";
  confirm_required: boolean;
};

export type ApiKnowledgeBuild = {
  id: string;
  project_id: string;
  build_no: string;
  status: "building" | "blocked" | "draft" | "published";
  status_label: string;
  build_type: string;
  summary: string;
  change_summary: string;
  source_document_version_ids: string[];
  exploration_run_ids: string[];
  blockers: string[];
  affected_modules: string[];
  output_dir: string;
  page_count: number;
  item_count: number;
  lint_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  available_actions: ApiAvailableAction[];
};

export type ApiWikiPage = {
  id: string;
  title: string;
  relative_path: string;
  page_type: string;
  module_key: string;
  summary: string;
  source_refs: unknown[];
  created_at: string;
};

export type ApiKnowledgeBuildDetail = {
  build: ApiKnowledgeBuild;
  pages: ApiWikiPage[];
  lint_issues: Array<{ id: string; severity: string; title: string; detail: string; page_id: string }>;
  source_refs: Array<{ id: string; source_type: string; source_id: string; source_title: string; location: string; excerpt: string }>;
};

export type ApiGlobalKnowledgeDocument = {
  id: string;
  name: string;
  knowledge_type: string;
  knowledge_type_label: string;
  version: string;
  scope: string;
  source_note?: string;
  description: string;
  status: "processing" | "available" | "conversion_failed" | "archived";
  status_label: string;
  current_version_id?: string | null;
  markdown_content?: string;
  file_count: number;
  created_by: string;
  created_at?: string;
  updated_at: string;
  archived_at?: string | null;
  available_actions: ApiAvailableAction[];
};

export type ApiGlobalKnowledgeVersion = {
  id: string;
  document_id: string;
  version_no: string;
  markdown_content: string;
  markdown_path: string;
  change_summary: string;
  conversion_status: string;
  conversion_summary: string;
  created_by: string;
  created_at: string;
};

export type ApiGlobalKnowledgeFile = {
  id: string;
  version_id: string;
  original_filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  created_at: string;
};

export type ApiGlobalKnowledgeList = {
  items: ApiGlobalKnowledgeDocument[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
  };
  filters: {
    knowledge_types: Array<{ value: string; label: string }>;
    statuses: Array<{ value: string; label: string }>;
  };
};

export type ApiGlobalKnowledgeDetail = {
  document: ApiGlobalKnowledgeDocument;
  current_version: ApiGlobalKnowledgeVersion | null;
  files: ApiGlobalKnowledgeFile[];
  versions: ApiGlobalKnowledgeVersion[];
  usage_logs: Array<{ id: string; usage_type: string; target_project_id: string | null; target_object_id: string; summary: string; created_at: string }>;
  available_actions: ApiAvailableAction[];
};

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
    const detail = payload?.detail;
    throw new Error(detail?.message ?? "请求失败，请稍后重试。");
  }

  return (payload as ApiEnvelope<T>).data;
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
    const detail = payload?.detail;
    throw new Error(detail?.message ?? "请求失败，请稍后重试。");
  }

  return response.blob();
}

export async function apiFormRequest<T>(path: string, formData: FormData, options: RequestInit = {}): Promise<T> {
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
    body: formData,
    headers,
  });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(detail?.message ?? "请求失败，请稍后重试。");
  }

  return (payload as ApiEnvelope<T>).data;
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
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").slice(0, 19);
}

export function operationLogActionToLabel(action: string) {
  return (
    {
      archive: "归档",
      cancel: "取消",
      confirm: "确认",
      create: "新增",
      delete: "删除",
      export: "导出",
      login: "登录",
      logout: "登出",
      merge: "归并",
      restore: "恢复",
      retry: "重试",
      run: "执行",
      update: "编辑",
      upload: "上传",
    } as Record<string, string>
  )[action] ?? action;
}

export function operationLogResultToLabel(result: string) {
  return (
    {
      cancelled: "已取消",
      failed: "失败",
      partial_success: "部分成功",
      success: "成功",
    } as Record<string, string>
  )[result] ?? result;
}

export function operationLogModuleToLabel(module: string) {
  return (
    {
      agent: "Agent",
      auth: "登录认证",
      model: "模型配置",
      project: "项目",
      requirement: "需求",
      system_setting: "系统设置",
      task: "任务",
    } as Record<string, string>
  )[module] ?? module;
}
