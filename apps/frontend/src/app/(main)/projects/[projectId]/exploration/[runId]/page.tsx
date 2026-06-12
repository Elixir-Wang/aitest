"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { useParams } from "next/navigation";

import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileText,
  Loader2,
  Pencil,
  Play,
  RefreshCw,
  Route,
  Save,
  Search,
  Square,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { AgentPlan, type AgentPlanStatus, type AgentPlanTask } from "@/components/ui/agent-plan";
import { AiEditInput } from "@/components/ui/ai-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { API_BASE_URL, apiAuthHeaders, apiRequest, formatDateTime, parseApiTimestamp } from "@/lib/api-client";
import { reportError as reportApiError } from "@/lib/error-feedback";
import { cn } from "@/lib/utils";

type ExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  environment_site_url: string;
  title: string;
  status: string;
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  goal: string;
  notes: string;
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
  artifact_root: string;
  result_summary: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  available_actions: string[];
};

type ExplorationRunDetail = {
  run: ExplorationRun;
  artifact_schema_version: number;
  unsupported_artifact: boolean;
  unsupported_reason: string;
  goal_validation?: ExplorationGoalValidation;
  exploration_plan?: ExplorationPlan;
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
    elements: Array<{
      id: string;
      page_id: string | null;
      element_name: string;
      element_type: string;
      recommended_locator: string;
      fallback_locator: string;
      stability_note: string;
      source_ref: string;
      primary_selector: ExplorationSelector;
      fallback_selector: ExplorationSelector;
    }>;
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

type ExplorationGoalValidation = {
  goal: string;
  status: string;
  summary: string;
  stats?: Record<string, unknown>;
  items?: Array<Record<string, unknown>>;
};

type ExplorationPlanStatus = "not_generated" | "draft" | "confirmed" | "running" | "completed" | "blocked";

type ExplorationPlan = {
  artifact_schema_version: number;
  plan_status: "not_generated" | "draft" | "confirmed" | "running" | "completed" | "blocked";
  business_boundary: string;
  goal: string;
  summary: string;
  items: ExplorationPlanItem[];
};

type ExplorationPlanItem = {
  id: string;
  business_module: string;
  capability_type: string;
  title: string;
  steps: string[];
  exploration_points: string[];
};

type DocumentEditResponse = {
  edited_content: string;
  change_summary: string;
};

type ExplorationStep = {
  id: string;
  type: string;
  title: string;
  detail?: string;
  status?: AgentPlanStatus;
  occurred_at?: string | null;
  artifact_path?: string;
  source?: string;
};

type ExplorationPage = ExplorationRunDetail["modules"][number]["pages"][number];

type ExplorationReport = {
  run_id: string;
  version_no: number | null;
  title: string;
  markdown_content: string;
  change_summary: string;
  created_at: string | null;
  artifact_schema_version: number;
  unsupported_artifact: boolean;
  unsupported_reason: string;
};

type ExplorationSelector = {
  kind?: string;
  code?: string;
  confidence?: string;
  reason?: string;
  verification?: {
    checked?: boolean;
    unique?: boolean;
    visible?: boolean;
    match_count?: number;
    reason?: string;
  };
  [key: string]: unknown;
};

type ExplorationLog = {
  run_id: string;
  log_content: string;
  log_path: string;
  updated_at: string | null;
  items?: ApiExplorationLogItem[];
  total?: number;
  page?: number;
  page_size?: number;
};

type ApiExplorationLogItem = {
  id: string;
  timestamp: string;
  event: string;
  event_label: string;
  category: string;
  level: string;
  page_id: string;
  page_title: string;
  url: string;
  action_name: string;
  result: string;
  source_label?: string;
  target_label?: string;
  artifact_path: string;
  summary: string;
  raw: string;
  payload: Record<string, unknown>;
};

type ExplorationStreamEvent = {
  type: string;
  run_id: string;
  payload: Record<string, unknown>;
};

type ProjectEnvironment = {
  id: string;
  project_id: string;
  name: string;
};

type ExplorationForm = {
  title: string;
  environmentId: string;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};

type ParsedLogEntry = {
  id: string;
  timestamp: string;
  type: string;
  typeLabel: string;
  category: LogCategory;
  level: LogLevel;
  pageId: string;
  pageTitle: string;
  url: string;
  actionName: string;
  result: string;
  sourceLabel: string;
  targetLabel: string;
  artifactPath: string;
  summary: string;
  raw: string;
  payload: Record<string, unknown>;
};

type LogCategory = "all" | "run" | "page" | "action" | "artifact" | "blocked" | "error" | "raw";
type LogLevel = "all" | "info" | "warning" | "error";
type PageItem = number | "ellipsis-start" | "ellipsis-end";

const statusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  stopping: "正在停止",
  cancelled: "已中止",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const goalValidationStatusLabels: Record<string, string> = {
  pending: "待验证",
  passed: "已通过",
  partial: "部分完成",
  failed: "未通过",
  skipped: "已跳过",
};

const explorationPlanStatusLabels: Record<ExplorationPlanStatus, string> = {
  not_generated: "未生成",
  draft: "待确认",
  confirmed: "已确认",
  running: "探索中",
  completed: "已完成",
  blocked: "有阻塞",
};

const loginStrategyLabels: Record<string, string> = {
  account_password: "账号密码",
  skip_login: "无需登录",
};

const logTypeLabels: Record<string, string> = {
  run_started: "探索开始",
  login_started: "登录开始",
  login_completed: "登录完成",
  page_discovered: "发现页面",
  page_visited: "访问页面",
  page_captured: "采集页面",
  accessibility_captured: "生成无障碍树",
  observe: "观察页面",
  action_detected: "发现动作",
  action_executed: "执行动作",
  agent_observed: "Agent 观察",
  agent_decision: "Agent 决策",
  agent_decision_fallback: "Agent 决策降级",
  action_started: "开始动作",
  action_result: "动作结果",
  action_completed: "动作完成",
  edge_created: "记录关系",
  artifact_written: "写入产物",
  blocked: "探索阻塞",
  skipped: "跳过",
  error: "错误",
  run_completed: "探索完成",
  raw: "原始日志",
};

const logCategoryLabels: Record<LogCategory, string> = {
  all: "全部类型",
  run: "运行",
  page: "页面",
  action: "动作",
  artifact: "产物",
  blocked: "阻塞",
  error: "错误",
  raw: "原始",
};

const logLevelLabels: Record<LogLevel, string> = {
  all: "全部级别",
  info: "信息",
  warning: "警告",
  error: "错误",
};

const logCategoryOptions: LogCategory[] = ["all", "run", "page", "action", "artifact", "blocked", "error", "raw"];
const logLevelOptions: LogLevel[] = ["all", "info", "warning", "error"];

const autoRefreshStatuses = new Set(["queued", "running", "stopping", "in-progress"]);
const stoppableStatuses = new Set(["queued", "running"]);
const explorationPlaceholders = {
  scope: "填写本次要探索的页面范围，例如全站、指定菜单、指定 URL 或核心模块。",
  forbiddenPaths: "填写禁止进入或点击的路径/动作，例如删除、支付、外发、批量通知、退出登录。",
  goal: "填写本次探索要验证的目标，例如遍历元素和链接，检查 401/403、登录跳转和异常页。",
};
const emptyExplorationForm: ExplorationForm = {
  title: "",
  environmentId: "",
  scope: "",
  forbiddenPaths: "",
  goal: "",
  notes: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};

function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function getVisiblePages(currentPage: number, pageCount: number): PageItem[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "ellipsis-end", pageCount];
  }

  if (currentPage >= pageCount - 3) {
    return [1, "ellipsis-start", pageCount - 4, pageCount - 3, pageCount - 2, pageCount - 1, pageCount];
  }

  return [1, "ellipsis-start", currentPage - 1, currentPage, currentPage + 1, "ellipsis-end", pageCount];
}

function parseStreamEvent(chunk: string): ExplorationStreamEvent | null {
  const lines = chunk.split("\n");
  const dataLine = lines.find((line) => line.startsWith("data:"));
  if (!dataLine) {
    return null;
  }
  const raw = dataLine.replace(/^data:\s*/, "");
  try {
    const parsed = JSON.parse(raw) as ExplorationStreamEvent;
    if (!parsed || typeof parsed.type !== "string" || typeof parsed.run_id !== "string") {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function applyStreamEvent(
  event: ExplorationStreamEvent,
  setters: {
    setStreamDetail: React.Dispatch<React.SetStateAction<ExplorationRunDetail | null>>;
    setRun: React.Dispatch<React.SetStateAction<ExplorationRun | null>>;
  },
) {
  if (
    event.type === "run_started" ||
    event.type === "run_completed" ||
    event.type === "run_failed" ||
    event.type === "run_cancelled"
  ) {
    setters.setRun((current) => (current ? { ...current, ...(event.payload as Partial<ExplorationRun>) } : current));
    setters.setStreamDetail((current) =>
      current ? { ...current, run: { ...current.run, ...(event.payload as Partial<ExplorationRun>) } } : current,
    );
  }
  if (event.type.startsWith("module_")) {
    setters.setStreamDetail((current) => mergeModuleEvent(current, event));
  } else if (event.type.startsWith("page_")) {
    setters.setStreamDetail((current) => mergePageEvent(current, event));
  } else if (event.type === "step_recorded") {
    setters.setStreamDetail((current) => mergeStepEvent(current, event));
  } else if (event.type === "blocker_detected") {
    setters.setStreamDetail((current) => mergeBlockerEvent(current, event));
  }
}

function mergeModuleEvent(
  detail: ExplorationRunDetail | null,
  event: ExplorationStreamEvent,
): ExplorationRunDetail | null {
  if (!detail) {
    return detail;
  }
  const payload = event.payload as Record<string, unknown>;
  const moduleId = String(payload.module_id || payload.module_key || "");
  if (!moduleId) {
    return detail;
  }
  const moduleIndex = detail.modules.findIndex((module) => module.id === moduleId || module.module_key === moduleId);
  const nextModule = {
    id: moduleId,
    module_key: String(payload.module_key || moduleId),
    module_name: String(payload.module_name || "未命名模块"),
    entry_path: String(payload.entry_path || ""),
    planned_page_count: Number(payload.planned_page_count || 0),
    explored_page_count: Number(payload.explored_page_count || 0),
    blocked_page_count: Number(payload.blocked_page_count || 0),
    action_count: Number(payload.action_count || 0),
    field_count: Number(payload.field_count || 0),
    state_transition_count: Number(payload.state_transition_count || 0),
    completion_status: String(payload.completion_status || "pending"),
    pages: moduleIndex >= 0 ? detail.modules[moduleIndex].pages : [],
    elements: moduleIndex >= 0 ? detail.modules[moduleIndex].elements : [],
    blockers: moduleIndex >= 0 ? detail.modules[moduleIndex].blockers : [],
  };
  const modules = [...detail.modules];
  if (moduleIndex >= 0) {
    modules[moduleIndex] = { ...modules[moduleIndex], ...nextModule };
  } else {
    modules.unshift(nextModule);
  }
  return { ...detail, modules };
}

function mergePageEvent(
  detail: ExplorationRunDetail | null,
  event: ExplorationStreamEvent,
): ExplorationRunDetail | null {
  if (!detail) {
    return detail;
  }
  const payload = event.payload as Record<string, unknown>;
  const moduleId = String(payload.module_key || payload.module_id || "");
  const pageId = String(payload.page_id || "");
  if (!moduleId || !pageId) {
    return detail;
  }
  const modules = detail.modules.map((module) => {
    if (module.id !== moduleId && module.module_key !== moduleId) {
      return module;
    }
    const existingIndex = module.pages.findIndex((page) => page.id === pageId);
    const existingPage = existingIndex >= 0 ? module.pages[existingIndex] : null;
    const incomingSteps = normalizeExplorationSteps(payload.steps);
    const page = {
      id: pageId,
      title: String(payload.title || "未命名页面"),
      url: String(payload.url || ""),
      entry_path: String(payload.entry_path || ""),
      yaml_path: String(payload.yaml_path || ""),
      status: String(payload.status || "explored"),
      blocker_reason: String(payload.blocker_reason || ""),
      recent_event: String(payload.recent_event || ""),
      structure_summary: String(payload.structure_summary || ""),
      steps: incomingSteps.length > 0 ? incomingSteps : existingPage?.steps || [],
    };
    const pages = [...module.pages];
    if (existingIndex >= 0) {
      pages[existingIndex] = { ...pages[existingIndex], ...page };
    } else {
      pages.push(page);
    }
    return { ...module, pages };
  });
  return { ...detail, modules };
}

function mergeStepEvent(
  detail: ExplorationRunDetail | null,
  event: ExplorationStreamEvent,
): ExplorationRunDetail | null {
  if (!detail) {
    return detail;
  }
  const payload = event.payload as Record<string, unknown>;
  const moduleId = String(payload.module_key || payload.module_id || "");
  const pageId = String(payload.page_id || "");
  const step = normalizeExplorationStep(payload.step, 1);
  if (!moduleId || !pageId || !step) {
    return detail;
  }
  const modules = detail.modules.map((module) => {
    if (module.id !== moduleId && module.module_key !== moduleId) {
      return module;
    }
    const pages = module.pages.map((page) => {
      if (page.id !== pageId) {
        return page;
      }
      const currentSteps = page.steps || [];
      const existingIndex = currentSteps.findIndex((item) => item.id === step.id);
      const steps = [...currentSteps];
      if (existingIndex >= 0) {
        steps[existingIndex] = step;
      } else {
        steps.push(step);
      }
      return { ...page, steps, recent_event: step.detail ?? step.title };
    });
    return { ...module, pages };
  });
  return { ...detail, modules };
}

function normalizeExplorationSteps(value: unknown): ExplorationStep[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => normalizeExplorationStep(item, index + 1))
    .filter((item): item is ExplorationStep => Boolean(item));
}

function normalizeExplorationStep(value: unknown, index: number): ExplorationStep | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const item = value as Record<string, unknown>;
  return {
    id: String(item.id || `step-${String(index).padStart(3, "0")}`),
    type: String(item.type || "event"),
    title: String(item.title || item.detail || "探索步骤"),
    detail: String(item.detail || ""),
    status: normalizeAgentPlanStatus(String(item.status || "completed")),
    occurred_at: item.occurred_at ? String(item.occurred_at) : null,
    artifact_path: String(item.artifact_path || ""),
    source: String(item.source || ""),
  };
}

function mergeBlockerEvent(
  detail: ExplorationRunDetail | null,
  event: ExplorationStreamEvent,
): ExplorationRunDetail | null {
  if (!detail) {
    return detail;
  }
  const payload = event.payload as Record<string, unknown>;
  const moduleId = String(payload.module_key || payload.module_id || "");
  const blocker = {
    id: `${event.type}-${String(payload.page_ref || payload.reason_type || "blocker")}`,
    page_ref: String(payload.page_ref || ""),
    reason_type: String(payload.reason_type || "unknown"),
    reason: String(payload.reason || ""),
    suggested_action: String(payload.suggested_action || ""),
    is_blocking: true,
  };
  const modules = detail.modules.map((module) => {
    if (module.id !== moduleId && module.module_key !== moduleId) {
      return module;
    }
    return { ...module, blockers: [...module.blockers, blocker] };
  });
  return { ...detail, modules };
}

function buildAgentPlanTasks(detail: ExplorationRunDetail | null): AgentPlanTask[] {
  if (!detail) {
    return [];
  }
  const hideEmptyPlanModules = isTerminalStatus(detail.run.status);
  return detail.modules
    .filter((module) => !(hideEmptyPlanModules && isEmptyPlannedModule(module)))
    .map((module) => ({
      id: module.id,
      title: module.module_name || "未命名模块",
      status: resolveModulePlanStatus(detail.run.status, module.completion_status),
      meta: [
        `${module.explored_page_count}/${Math.max(module.planned_page_count, module.explored_page_count, 1)} 页面`,
      ],
      subtasks: module.pages.map((page) => ({
        id: page.id,
        title: buildExplorationPageTaskTitle(page),
        description: page.recent_event || page.structure_summary || page.blocker_reason || "",
        status: resolvePagePlanStatus(page),
        meta: buildExplorationPageTaskMeta(page),
        steps: page.steps,
      })),
    }));
}

function resolvePagePlanStatus(page: ExplorationPage): AgentPlanStatus {
  const normalizedPageStatus = normalizeAgentPlanStatus(page.status || "pending");
  if (normalizedPageStatus !== "running") {
    return normalizedPageStatus;
  }
  const actionStep = [...(page.steps ?? [])].reverse().find((step) => step.type === "action_result");
  if (!actionStep) {
    return normalizedPageStatus;
  }
  const actionStatus = normalizeAgentPlanStatus(actionStep.status || "completed");
  return actionStatus === "running" || actionStatus === "pending" ? "completed" : actionStatus;
}

function buildExplorationPageTaskTitle(page: ExplorationPage): string {
  const steps = page.steps ?? [];
  const actionStep = [...steps].reverse().find((step) => step.type === "action_result" && step.detail);
  if (actionStep?.detail) {
    return formatActionStepTitle(actionStep.detail);
  }
  const decisionStep = [...steps].reverse().find((step) => step.type === "agent_decision" && step.detail);
  if (decisionStep?.detail) {
    return `决策：${compactText(decisionStep.detail)}`;
  }
  return page.url || page.entry_path || page.title || "未命名页面";
}

function buildExplorationPageTaskMeta(page: ExplorationPage): string[] {
  const meta = [page.title, page.url || page.entry_path].filter((item): item is string => Boolean(item));
  return Array.from(new Set(meta));
}

function formatActionStepTitle(detail: string): string {
  const firstSentence = detail.split(/[，。]/)[0] ?? detail;
  const withoutStatus = firstSentence.replace(
    /\s*[：:]\s*(passed|failed|skipped|completed|unknown|unverified)\s*$/i,
    "",
  );
  const actionMatch = withoutStatus.match(/^(click|fill|navigate|go_back|close_modal|wait)\s+(.+)$/i);
  if (!actionMatch) {
    return compactText(withoutStatus || detail);
  }
  const actionLabels: Record<string, string> = {
    click: "点击",
    fill: "填写",
    navigate: "跳转",
    go_back: "返回",
    close_modal: "关闭弹窗",
    wait: "等待",
  };
  const action = actionLabels[actionMatch[1].toLowerCase()] ?? actionMatch[1];
  return `${action}：${compactText(actionMatch[2])}`;
}

function compactText(value: string, maxLength = 48): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}...` : normalized;
}

function formatPlanItemsDraft(items: ExplorationPlanItem[] = []): string {
  return JSON.stringify(items, null, 2);
}

function parsePlanItemsDraft(draft: string): ExplorationPlanItem[] {
  const parsed = JSON.parse(draft) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("计划内容必须是计划项数组。");
  }
  if (!parsed.length) {
    throw new Error("探索计划至少需要一个计划项。");
  }
  return parsed.map((item, index) => normalizePlanDraftItem(item, index));
}

function normalizeExplorationRunDetail(data: ExplorationRunDetail): ExplorationRunDetail {
  return {
    ...data,
    exploration_plan: normalizeExplorationPlan(data.exploration_plan),
  };
}

function normalizeExplorationPlan(plan: ExplorationPlan | undefined): ExplorationPlan | undefined {
  if (!plan) {
    return undefined;
  }
  const items = Array.isArray(plan.items)
    ? plan.items
        .filter((item): item is ExplorationPlanItem => Boolean(item) && typeof item === "object")
        .map((item, index) => normalizePlanDisplayItem(item, index))
    : [];
  return {
    ...plan,
    items,
  };
}

function normalizePlanDisplayItem(item: ExplorationPlanItem, index: number): ExplorationPlanItem {
  const record = item as Record<string, unknown>;
  return {
    id: optionalPlanText(record.id) || `plan-item-${index + 1}`,
    business_module: optionalPlanText(record.business_module) || "未命名模块",
    capability_type: optionalPlanText(record.capability_type) || "custom",
    title: optionalPlanText(record.title) || "未命名计划项",
    steps: planTextList(record.steps),
    exploration_points: planTextList(record.exploration_points),
  };
}

function normalizePlanDraftItem(item: unknown, index: number): ExplorationPlanItem {
  if (!item || typeof item !== "object" || Array.isArray(item)) {
    throw new Error(`第 ${index + 1} 个计划项必须是对象。`);
  }
  const record = item as Record<string, unknown>;
  const title = requiredPlanText(record.title, index, "title");
  const businessModule = requiredPlanText(record.business_module, index, "business_module");
  const capabilityType = requiredPlanText(record.capability_type, index, "capability_type");
  return {
    id: optionalPlanText(record.id) || `plan-custom-${index + 1}`,
    business_module: businessModule,
    capability_type: capabilityType,
    title,
    steps: planTextList(record.steps),
    exploration_points: planTextList(record.exploration_points),
  };
}

function requiredPlanText(value: unknown, index: number, field: string): string {
  const text = optionalPlanText(value);
  if (!text) {
    throw new Error(`第 ${index + 1} 个计划项缺少 ${field}。`);
  }
  return text;
}

function optionalPlanText(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function planTextList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => optionalPlanText(item)).filter(Boolean);
}

function isEmptyPlannedModule(module: ExplorationRunDetail["modules"][number]): boolean {
  return (
    module.module_key.startsWith("planned-") &&
    module.explored_page_count === 0 &&
    module.blocked_page_count === 0 &&
    module.action_count === 0 &&
    module.field_count === 0 &&
    module.state_transition_count === 0 &&
    module.pages.length === 0 &&
    module.elements.length === 0 &&
    module.blockers.length === 0
  );
}

function resolveModulePlanStatus(runStatus: string, moduleStatus: string): AgentPlanStatus {
  const normalizedModuleStatus = normalizeAgentPlanStatus(moduleStatus);
  const canFollowRunStatus = normalizedModuleStatus === "pending" || normalizedModuleStatus === "running";
  if (isActiveStatus(runStatus) && canFollowRunStatus) {
    return normalizeAgentPlanStatus(runStatus);
  }
  if (isTerminalStatus(runStatus) && normalizedModuleStatus === "running") {
    return normalizeAgentPlanStatus(runStatus);
  }
  return normalizedModuleStatus;
}

function normalizeAgentPlanStatus(status: string): AgentPlanStatus {
  if (status === "running" || status === "queued" || status === "in-progress") {
    return "running";
  }
  if (status === "stopping") {
    return "stopping";
  }
  if (status === "blocked") {
    return "blocked";
  }
  if (status === "cancelled") {
    return "cancelled";
  }
  if (status === "partial") {
    return "partial";
  }
  if (status === "failed") {
    return "failed";
  }
  if (status === "completed") {
    return "completed";
  }
  if (status === "explored") {
    return "completed";
  }
  return "pending";
}

function isActiveStatus(status: string): boolean {
  return autoRefreshStatuses.has(status);
}

function isTerminalStatus(status: string): boolean {
  return ["completed", "partial", "blocked", "cancelled", "failed"].includes(status);
}

function hasExplorationStarted(run: ExplorationRun): boolean {
  return (
    run.started_at !== null ||
    run.finished_at !== null ||
    run.artifact_root.length > 0 ||
    run.result_summary.length > 0 ||
    run.status !== "pending"
  );
}

export default function Page() {
  const params = useParams<{ projectId: string; runId: string }>();
  const projectName = useProjectName(params.projectId);
  const [run, setRun] = useState<ExplorationRun | null>(null);
  const [detail, setDetail] = useState<ExplorationRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [planAction, setPlanAction] = useState<"generate" | "confirm" | "save" | "">("");
  const [planActionStartedAt, setPlanActionStartedAt] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [failureVisible, setFailureVisible] = useState(true);
  const [activeTab, setActiveTab] = useState("探索概览");
  const [report, setReport] = useState<ExplorationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [log, setLog] = useState<ExplorationLog | null>(null);
  const [logError, setLogError] = useState("");
  const [streamDetail, setStreamDetail] = useState<ExplorationRunDetail | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [environments, setEnvironments] = useState<ProjectEnvironment[]>([]);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [explorationForm, setExplorationForm] = useState<ExplorationForm>(emptyExplorationForm);
  const [durationNow, setDurationNow] = useState(() => Date.now());
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importingFromRequirement, setImportingFromRequirement] = useState(false);

  const loadRun = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }
      setError("");
      setFailureVisible(true);
      try {
        const data = await apiRequest<ExplorationRunDetail>(
          `/projects/${params.projectId}/exploration-runs/${params.runId}/detail`,
        );
        const normalizedData = normalizeExplorationRunDetail(data);
        setDetail(normalizedData);
        setStreamDetail(normalizedData);
        setRun(normalizedData.run);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "探索任务加载失败");
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [params.projectId, params.runId],
  );

  useEffect(() => {
    void loadRun();
  }, [loadRun]);

  const runStatus = run?.status;

  useEffect(() => {
    const runStartedAt = run?.started_at ?? null;
    const runFinishedAt = run?.finished_at ?? null;
    const runStatus = run?.status;

    const shouldTickRunDuration = Boolean(runStartedAt && !runFinishedAt && runStatus && isActiveStatus(runStatus));

    if (!shouldTickRunDuration && !planActionStartedAt) {
      return undefined;
    }

    setDurationNow(Date.now());
    const timer = window.setInterval(() => {
      setDurationNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [planActionStartedAt, run]);

  useEffect(() => {
    if (!runStatus || !autoRefreshStatuses.has(runStatus)) {
      return undefined;
    }

    let cancelled = false;
    let controller: AbortController | null = null;
    let retryTimer: number | null = null;

    const openStream = async () => {
      controller = new AbortController();
      try {
        const headers = apiAuthHeaders();
        const response = await fetch(
          `${API_BASE_URL}/projects/${params.projectId}/exploration-runs/${params.runId}/stream`,
          {
            headers,
            signal: controller.signal,
          },
        );

        if (!response.ok || !response.body) {
          throw new Error("探索实时流连接失败");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) {
            void loadRun({ silent: true });
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split("\n\n");
          buffer = chunks.pop() || "";
          for (const chunk of chunks) {
            const event = parseStreamEvent(chunk);
            if (!event) {
              continue;
            }
            applyStreamEvent(event, { setStreamDetail, setRun });
          }
        }
      } catch {
        if (cancelled || controller?.signal.aborted) {
          return;
        }
        retryTimer = window.setTimeout(() => {
          void openStream();
        }, 1500);
      }
    };

    void openStream();

    return () => {
      cancelled = true;
      controller?.abort();
      if (retryTimer) {
        window.clearTimeout(retryTimer);
      }
    };
  }, [loadRun, params.projectId, params.runId, runStatus]);

  const loadReport = useCallback(async () => {
    setReportLoading(true);
    setReportError("");
    try {
      const data = await apiRequest<ExplorationReport>(
        `/projects/${params.projectId}/exploration-runs/${params.runId}/report`,
      );
      setReport(data);
    } catch (requestError) {
      setReportError(requestError instanceof Error ? requestError.message : "探索报告加载失败");
    } finally {
      setReportLoading(false);
    }
  }, [params.projectId, params.runId]);

  useEffect(() => {
    if (activeTab === "探索报告") {
      void loadReport();
    }
  }, [activeTab, loadReport]);

  const loadLog = useCallback(async () => {
    try {
      const data = await apiRequest<ExplorationLog>(
        `/projects/${params.projectId}/exploration-runs/${params.runId}/log`,
      );
      setLog(data);
    } catch (requestError) {
      setLogError(requestError instanceof Error ? requestError.message : "探索日志加载失败");
    }
  }, [params.projectId, params.runId]);

  useEffect(() => {
    if (activeTab === "探索日志") {
      void loadLog();
    }
  }, [activeTab, loadLog]);

  function clearExplorationOutputs() {
    setDetail(null);
    setStreamDetail(null);
    setReport(null);
    setReportError("");
    setReportLoading(false);
    setLog(null);
    setLogError("");
  }

  async function startExploration() {
    if (!run) {
      return;
    }
    const restarting = hasExplorationStarted(run);
    setStarting(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/start`, {
        method: "POST",
      });
      setRun(updated);
      clearExplorationOutputs();
      notifyAiTaskStarted();
      toast.success(restarting ? "重新探索已开始" : "探索任务已开始");
      window.setTimeout(() => void loadRun({ silent: true }), 800);
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索任务启动失败",
        actionLabel: restarting ? "重新探索" : "启动探索任务",
        method: "POST",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/start`,
      });
    } finally {
      setStarting(false);
    }
  }

  function applyExplorationPlan(plan: ExplorationPlan) {
    const normalizedPlan = normalizeExplorationPlan(plan);
    setDetail((current) => (current ? { ...current, exploration_plan: normalizedPlan } : current));
    setStreamDetail((current) => (current ? { ...current, exploration_plan: normalizedPlan } : current));
  }

  function clearGeneratedExplorationPlanModules() {
    setDetail((current) =>
      current ? { ...current, modules: current.modules.filter((module) => !isEmptyPlannedModule(module)) } : current,
    );
    setStreamDetail((current) =>
      current ? { ...current, modules: current.modules.filter((module) => !isEmptyPlannedModule(module)) } : current,
    );
  }

  function clearStaleExplorationPlan() {
    const clearPlan = (current: ExplorationRunDetail | null) => {
      if (!current?.exploration_plan) {
        return current;
      }
      return {
        ...current,
        exploration_plan: {
          ...current.exploration_plan,
          plan_status: "not_generated" as ExplorationPlanStatus,
          summary: "正在生成新的探索计划，旧计划已清除。",
          items: [],
        },
      };
    };

    setDetail(clearPlan);
    setStreamDetail(clearPlan);
  }

  async function generateExplorationPlan() {
    if (!run) {
      return;
    }
    setPlanAction("generate");
    clearGeneratedExplorationPlanModules();
    clearStaleExplorationPlan();
    setPlanActionStartedAt(Date.now());
    try {
      toast.info("正在生成探索计划，此操作在当前页面执行，不会进入任务中心");
      const plan = await apiRequest<ExplorationPlan>(
        `/projects/${run.project_id}/exploration-runs/${run.id}/plan/generate`,
        { method: "POST" },
      );
      applyExplorationPlan(plan);
      toast.success("探索计划已生成，请确认或补充后再开始探索");
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索计划生成失败",
        actionLabel: "生成探索计划",
        method: "POST",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/plan/generate`,
      });
    } finally {
      setPlanAction("");
      setPlanActionStartedAt(null);
    }
  }

  async function importPlanFromRequirement(requirementDocId: string, requirementRunId: string) {
    if (!run) {
      return;
    }
    setImportingFromRequirement(true);
    clearGeneratedExplorationPlanModules();
    clearStaleExplorationPlan();
    try {
      toast.info("正在从需求文档生成并导入探索计划...");

      // 先生成探索计划
      await apiRequest(
        `/projects/${run.project_id}/requirements/${requirementDocId}/analysis-runs/${requirementRunId}/exploration-plan/generate`,
        { method: "POST" }
      );

      // 然后导入到当前探索任务
      const plan = await apiRequest<ExplorationPlan>(
        `/projects/${run.project_id}/exploration-runs/${run.id}/plan/import-from-requirement`,
        {
          method: "POST",
          body: JSON.stringify({
            requirement_doc_id: requirementDocId,
            requirement_run_id: requirementRunId,
          }),
        }
      );

      applyExplorationPlan(plan);
      setImportDialogOpen(false);
      toast.success("探索计划已从需求导入，请确认或补充后再开始探索");
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "从需求导入探索计划失败",
        actionLabel: "导入探索计划",
        method: "POST",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/plan/import-from-requirement`,
      });
    } finally {
      setImportingFromRequirement(false);
    }
  }

  async function saveExplorationPlanItems(items: ExplorationPlanItem[]): Promise<boolean> {
    if (!run) {
      return false;
    }
    setPlanAction("save");
    try {
      const plan = await apiRequest<ExplorationPlan>(`/projects/${run.project_id}/exploration-runs/${run.id}/plan`, {
        method: "PATCH",
        body: JSON.stringify({ items }),
      });
      applyExplorationPlan(plan);
      toast.success("探索计划已保存");
      return true;
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索计划保存失败",
        actionLabel: "保存探索计划",
        method: "PATCH",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/plan`,
      });
      return false;
    } finally {
      setPlanAction("");
    }
  }

  async function confirmExplorationPlan(): Promise<boolean> {
    if (!run) {
      return false;
    }
    setPlanAction("confirm");
    try {
      const plan = await apiRequest<ExplorationPlan>(
        `/projects/${run.project_id}/exploration-runs/${run.id}/plan/confirm`,
        { method: "POST" },
      );
      applyExplorationPlan(plan);
      toast.success("探索计划已确认，可以按计划开始探索");
      return true;
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索计划确认失败",
        actionLabel: "确认探索计划",
        method: "POST",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/plan/confirm`,
      });
      return false;
    } finally {
      setPlanAction("");
    }
  }

  async function stopExploration() {
    if (!run) {
      return;
    }
    setStopping(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/stop`, {
        method: "POST",
      });
      setRun(updated);
      setDetail((current) => (current ? { ...current, run: updated } : current));
      setStopDialogOpen(false);
      toast.success("探索任务已停止");
      window.setTimeout(() => void loadRun({ silent: true }), 800);
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索任务停止失败",
        actionLabel: "停止探索任务",
        method: "POST",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/stop`,
      });
    } finally {
      setStopping(false);
    }
  }

  async function loadEnvironments() {
    setEnvironmentLoading(true);
    try {
      const data = await apiRequest<ProjectEnvironment[]>(`/projects/${params.projectId}/environments`);
      setEnvironments(data);
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "环境列表加载失败",
        actionLabel: "加载环境列表",
        method: "GET",
        path: `/projects/${params.projectId}/environments`,
      });
    } finally {
      setEnvironmentLoading(false);
    }
  }

  function openEditDialog() {
    if (!run) {
      return;
    }
    setExplorationForm({
      title: run.title,
      environmentId: run.environment_id,
      scope: run.scope,
      forbiddenPaths: run.forbidden_paths,
      goal: run.goal,
      notes: run.notes,
      maxPages: String(run.max_pages ?? 50),
      maxActions: String(run.max_actions ?? 1000),
      timeoutMinutes: String(run.timeout_minutes ?? 120),
    });
    setEditDialogOpen(true);
    if (environments.length === 0) {
      void loadEnvironments();
    }
  }

  async function saveExplorationRun() {
    if (!run) {
      return;
    }
    if (!explorationForm.title.trim() || !explorationForm.environmentId) {
      toast.error("请填写任务名称并选择环境");
      return;
    }
    const maxPages = parsePositiveInteger(explorationForm.maxPages);
    const maxActions = parsePositiveInteger(explorationForm.maxActions);
    const timeoutMinutes = parsePositiveInteger(explorationForm.timeoutMinutes);
    if (!maxPages || !maxActions || !timeoutMinutes) {
      toast.error("请填写大于 0 的执行边界");
      return;
    }

    setSaving(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          environment_id: explorationForm.environmentId,
          title: explorationForm.title,
          scope: explorationForm.scope,
          forbidden_paths: explorationForm.forbiddenPaths,
          goal: explorationForm.goal,
          notes: explorationForm.notes,
          max_pages: maxPages,
          max_actions: maxActions,
          timeout_minutes: timeoutMinutes,
        }),
      });
      setRun(updated);
      setDetail((current) => (current ? { ...current, run: updated } : current));
      setEditDialogOpen(false);
      toast.success("探索任务已更新");
      void loadRun({ silent: true });
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索任务更新失败",
        actionLabel: "更新探索任务",
        method: "PATCH",
        path: `/projects/${run.project_id}/exploration-runs/${run.id}`,
      });
    } finally {
      setSaving(false);
    }
  }

  const canStart = run ? ["pending", "partial", "completed", "blocked", "cancelled"].includes(run.status) : false;
  const canStop = run ? stoppableStatuses.has(run.status) : false;
  const canEdit = run ? !["queued", "running", "stopping"].includes(run.status) : false;
  const saveDisabled = !explorationForm.title.trim() || !explorationForm.environmentId || saving;
  const activeDetail = streamDetail ?? detail;
  const explorationPlan = activeDetail?.exploration_plan;
  const hasFirstDiscoveryArtifacts = activeDetail
    ? activeDetail.modules.some((module) => !hasNoModuleArtifacts(module))
    : false;
  const canStartFirstDiscovery = Boolean(run) && canStart && !hasFirstDiscoveryArtifacts;
  const canGeneratePlan = Boolean(run) && canEdit;
  const canStartFromPlan = explorationPlan?.plan_status === "confirmed" && Boolean(run) && canStart;
  const isUnsupportedArtifact = Boolean(activeDetail?.unsupported_artifact);
  const unsupportedArtifactReason = activeDetail?.unsupported_reason || "历史产物格式不支持新版详情，请重新探索。";
  const hasNoExplorationArtifacts = activeDetail
    ? activeDetail.modules.every((module) => hasNoModuleArtifacts(module))
    : false;
  const shouldShowNoArtifactNotice = Boolean(
    run && hasNoExplorationArtifacts && (run.status === "cancelled" || run.status === "blocked"),
  );
  const explorationDuration = run ? formatExplorationDuration(run, durationNow) : "-";
  const agentPlanTasks = buildAgentPlanTasks(activeDetail);
  const showRunActions = activeTab === "探索计划" || activeTab === "探索概览";
  const failureDetail = error
    ? {
        error,
        projectId: params.projectId,
        requestPath: `/projects/${params.projectId}/exploration-runs/${params.runId}/detail`,
        runId: params.runId,
        failedAt: formatDateTime(new Date().toISOString()),
      }
    : null;

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "探索", run?.title ?? "探索任务"]}
      description="查看探索任务运行概览、执行日志和探索报告。"
      tabActions={
        showRunActions ? (
          <>
            <Button disabled={loading} onClick={() => void loadRun()} size="sm" variant="outline">
              <RefreshCw className="size-4" />
              刷新
            </Button>
            <Button disabled={!canEdit} onClick={openEditDialog} size="sm" variant="outline">
              <Pencil className="size-4" />
              编辑
            </Button>
            {canStop ? (
              <Button disabled={stopping} onClick={() => setStopDialogOpen(true)} size="sm" variant="destructive">
                <Square className="size-4" />
                停止探索
              </Button>
            ) : null}
          </>
        ) : null
      }
      projectScope="project"
      activeTab={activeTab}
      onTabChange={setActiveTab}
      tabs={["探索计划", "探索概览", "探索日志", "探索报告"]}
      title={run?.title ?? "探索任务"}
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}

      {activeTab === "探索计划" ? (
        <ExplorationTaskPanel
          canEdit={canEdit}
          canGeneratePlan={canGeneratePlan}
          canStartFirstDiscovery={canStartFirstDiscovery}
          canStartFromPlan={canStartFromPlan}
          onConfirmPlan={confirmExplorationPlan}
          onGeneratePlan={generateExplorationPlan}
          onSavePlanItems={saveExplorationPlanItems}
          onStart={startExploration}
          plan={explorationPlan}
          planAction={planAction}
          planActionStartedAt={planActionStartedAt}
          planActionNow={durationNow}
          run={run}
          starting={starting}
        />
      ) : null}

      {activeTab === "探索概览" ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              helper="当前探索任务状态"
              icon={Route}
              label="任务状态"
              value={run ? (statusLabels[run.status] ?? run.status) : "-"}
            />
            <MetricCard
              helper="用于页面访问和探索执行"
              icon={Play}
              label="探索环境"
              value={run?.environment_name ?? "-"}
            />
            <MetricCard
              helper="最近一次状态变更"
              icon={RefreshCw}
              label="更新时间"
              value={run ? formatDateTime(run.updated_at) : "-"}
            />
            <MetricCard helper="从开始探索到结束的耗时" icon={FileText} label="探索时长" value={explorationDuration} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <ShellSection className="min-w-0">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-medium text-sm">探索模块进度</h2>
                  <p className="text-muted-foreground text-xs">展示模块、页面状态和页面探索步骤</p>
                </div>
              </div>
              {loading ? (
                <div className="py-10 text-center text-muted-foreground text-sm">探索任务加载中</div>
              ) : run ? (
                <div className="space-y-3">
                  {isUnsupportedArtifact ? (
                    <UnsupportedArtifactNotice
                      onOpenLog={() => setActiveTab("探索日志")}
                      onRestart={startExploration}
                      reason={unsupportedArtifactReason}
                      restarting={starting}
                    />
                  ) : shouldShowNoArtifactNotice ? (
                    <NoArtifactNotice run={run} onOpenLog={() => setActiveTab("探索日志")} />
                  ) : null}
                  {isUnsupportedArtifact ? null : (
                    <AgentPlan completedTaskDecoration="none" emptyLabel="暂无探索模块" tasks={agentPlanTasks} />
                  )}
                </div>
              ) : null}
            </ShellSection>

            <div className="min-w-0">
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="text-sm">执行时间线</CardTitle>
                  <CardDescription>按北京时间展示关键阶段</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <TimelineItem
                    active={Boolean(run)}
                    label="创建任务"
                    value={run ? formatDateTime(run.created_at) : "-"}
                  />
                  <TimelineItem
                    active={Boolean(run?.started_at)}
                    label="开始探索"
                    value={run?.started_at ? formatDateTime(run.started_at) : "待执行"}
                  />
                  <TimelineItem
                    active={Boolean(run?.finished_at)}
                    label={run?.status === "cancelled" ? "中止探索" : "完成探索"}
                    value={run?.finished_at ? formatDateTime(run.finished_at) : "等待结果"}
                  />
                </CardContent>
              </Card>
            </div>
          </div>

          {isUnsupportedArtifact ? null : <GoalValidationSection detail={activeDetail} run={run} />}
        </>
      ) : null}

      {activeTab === "探索日志" ? (
        <ExplorationLogPanel
          initialError={logError}
          initialLog={log}
          failureDetail={failureDetail}
          projectId={params.projectId}
          run={run}
          runId={params.runId}
        />
      ) : null}

      {activeTab === "探索报告" ? (
        <ExplorationReportPanel
          error={reportError}
          loading={reportLoading}
          onRestart={startExploration}
          report={report}
          restarting={starting}
        />
      ) : null}

      <Dialog onOpenChange={setEditDialogOpen} open={editDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>编辑探索任务</DialogTitle>
            <DialogDescription>调整任务名称、关联环境、探索范围、探索目标和禁止路径。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="exploration-title">任务名称</FieldLabel>
              <Input
                id="exploration-title"
                onChange={(event) => setExplorationForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="后台管理系统全站探索"
                value={explorationForm.title}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="exploration-environment">环境</FieldLabel>
              <Select
                disabled={environmentLoading}
                onValueChange={(value) => setExplorationForm((current) => ({ ...current, environmentId: value }))}
                value={explorationForm.environmentId}
              >
                <SelectTrigger className="w-full" id="exploration-environment">
                  <SelectValue placeholder={environmentLoading ? "环境加载中" : "选择环境"} />
                </SelectTrigger>
                <SelectContent>
                  {environments.map((environment) => (
                    <SelectItem key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-scope">探索范围</FieldLabel>
              <Textarea
                className="min-h-24"
                id="exploration-scope"
                onChange={(event) => setExplorationForm((current) => ({ ...current, scope: event.target.value }))}
                placeholder={explorationPlaceholders.scope}
                value={explorationForm.scope}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-forbidden-paths">禁止路径</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-forbidden-paths"
                onChange={(event) =>
                  setExplorationForm((current) => ({ ...current, forbiddenPaths: event.target.value }))
                }
                placeholder={explorationPlaceholders.forbiddenPaths}
                value={explorationForm.forbiddenPaths}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-goal">探索目标</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-goal"
                onChange={(event) => setExplorationForm((current) => ({ ...current, goal: event.target.value }))}
                placeholder={explorationPlaceholders.goal}
                value={explorationForm.goal}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-notes">备注</FieldLabel>
              <Textarea
                className="min-h-16"
                id="exploration-notes"
                onChange={(event) => setExplorationForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="补充说明，不参与探索目标判定"
                value={explorationForm.notes}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel>执行边界</FieldLabel>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-max-pages">
                  <span className="text-muted-foreground text-xs">页面上限</span>
                  <Input
                    id="exploration-edit-max-pages"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxPages: event.target.value }))
                    }
                    placeholder="50"
                    type="number"
                    value={explorationForm.maxPages}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-max-actions">
                  <span className="text-muted-foreground text-xs">操作上限</span>
                  <Input
                    id="exploration-edit-max-actions"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxActions: event.target.value }))
                    }
                    placeholder="1000"
                    type="number"
                    value={explorationForm.maxActions}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-timeout-minutes">
                  <span className="text-muted-foreground text-xs">超时时间（分钟）</span>
                  <Input
                    id="exploration-edit-timeout-minutes"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, timeoutMinutes: event.target.value }))
                    }
                    placeholder="120"
                    type="number"
                    value={explorationForm.timeoutMinutes}
                  />
                </label>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setEditDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={saveDisabled} onClick={saveExplorationRun} type="button">
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={setStopDialogOpen} open={stopDialogOpen}>
        <DialogContent className="gap-5 p-6 sm:max-w-md">
          <DialogHeader className="gap-3">
            <DialogTitle>停止探索任务</DialogTitle>
            <DialogDescription>停止后将终止当前浏览器探索进程，已生成的截图、日志和页面事实会保留。</DialogDescription>
          </DialogHeader>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setStopDialogOpen(false)} type="button" variant="outline">
              继续探索
            </Button>
            <Button disabled={stopping} onClick={stopExploration} type="button" variant="destructive">
              <Square className="size-4" />
              停止探索
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <RequirementImportDialog
        importingFromRequirement={importingFromRequirement}
        onImport={importPlanFromRequirement}
        onOpenChange={setImportDialogOpen}
        open={importDialogOpen}
        projectId={params.projectId}
      />
    </PageShell>
  );
}

function ExplorationTaskPanel({
  canEdit,
  canGeneratePlan,
  canStartFirstDiscovery,
  canStartFromPlan,
  onConfirmPlan,
  onGeneratePlan,
  onSavePlanItems,
  onStart,
  plan,
  planAction,
  planActionNow,
  planActionStartedAt,
  run,
  starting,
}: {
  canEdit: boolean;
  canGeneratePlan: boolean;
  canStartFirstDiscovery: boolean;
  canStartFromPlan: boolean;
  onConfirmPlan: () => Promise<boolean>;
  onGeneratePlan: () => Promise<void> | void;
  onSavePlanItems: (items: ExplorationPlanItem[]) => Promise<boolean>;
  onStart: () => Promise<void> | void;
  plan?: ExplorationPlan;
  planAction: "generate" | "confirm" | "save" | "";
  planActionNow: number;
  planActionStartedAt: number | null;
  run: ExplorationRun | null;
  starting: boolean;
}) {
  const loginStrategy = run ? (loginStrategyLabels[run.login_strategy] ?? run.login_strategy) : "-";
  const planStatus = plan?.plan_status ?? "not_generated";
  const planStatusLabel = explorationPlanStatusLabels[planStatus];
  const canGenerateDiscoveryPlan = canEdit && canGeneratePlan && !planAction;
  const canConfirmAndPreparePlan = canEdit && !planAction && Boolean(plan?.items.length) && planStatus !== "confirmed";
  const [editingPlan, setEditingPlan] = useState(false);
  const [editingPlanWithAi, setEditingPlanWithAi] = useState(false);
  const [readyToStartConfirmedPlan, setReadyToStartConfirmedPlan] = useState(false);
  const [planDraft, setPlanDraft] = useState(formatPlanItemsDraft(plan?.items ?? []));
  const [planDraftError, setPlanDraftError] = useState("");
  const generatingPlan = planAction === "generate";
  const generatingPlanElapsed =
    generatingPlan && planActionStartedAt ? formatElapsedDuration(planActionNow - planActionStartedAt) : "";
  const canEditPlanWithAi = canEdit && (plan?.items.length ?? 0) > 0 && !editingPlanWithAi && !planAction;
  const confirmAndStartDisabled =
    planStatus === "confirmed" ? !canStartFromPlan || starting : !canConfirmAndPreparePlan;
  const confirmAndStartLabel =
    planAction === "confirm"
      ? "确认中"
      : starting
        ? "启动中"
        : readyToStartConfirmedPlan
          ? "再次点击开始探索"
          : planStatus === "confirmed"
            ? "按计划开始探索"
            : "确认计划并准备探索";

  useEffect(() => {
    if (!editingPlan) {
      setPlanDraft(formatPlanItemsDraft(plan?.items ?? []));
      setPlanDraftError("");
    }
  }, [editingPlan, plan]);

  useEffect(() => {
    if (planStatus !== "confirmed") {
      setReadyToStartConfirmedPlan(false);
    }
  }, [planStatus]);

  async function savePlanDraft() {
    setPlanDraftError("");
    try {
      const items = parsePlanItemsDraft(planDraft);
      const saved = await onSavePlanItems(items);
      if (saved) {
        setEditingPlan(false);
      }
    } catch (error) {
      setPlanDraftError(error instanceof Error ? error.message : "探索计划格式不正确。");
    }
  }

  async function editPlanWithAi(instruction: string) {
    if (!plan?.items.length) {
      toast.error("请先生成探索计划");
      return;
    }
    setEditingPlanWithAi(true);
    try {
      const editResult = await apiRequest<DocumentEditResponse>("/agents/document-editor/run", {
        method: "POST",
        body: JSON.stringify({
          content: formatPlanItemsDraft(plan.items),
          instruction: [
            "请只修改下面的探索计划项 JSON 数组，并返回修改后的完整 JSON 数组。",
            "必须保留字段：id、business_module、capability_type、title、steps、exploration_points。",
            "title 使用中文功能名，steps 保持模块级探索内容，exploration_points 记录已发现入口或补充线索；不要把 capability_type 当作用户可见标题。",
            instruction,
          ].join("\n"),
        }),
      });
      if (!editResult.edited_content.trim()) {
        toast.info(editResult.change_summary || "AI 未修改探索计划");
        return;
      }
      const items = parsePlanItemsDraft(editResult.edited_content);
      const saved = await onSavePlanItems(items);
      if (saved) {
        toast.success(editResult.change_summary.trim() ? editResult.change_summary : "AI 修改当前计划已保存");
      }
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "AI 修改探索计划失败",
        actionLabel: "AI 修改当前计划",
        method: "POST",
        path: "/agents/document-editor/run",
      });
    } finally {
      setEditingPlanWithAi(false);
    }
  }

  async function confirmPlanThenStart() {
    if (planStatus !== "confirmed") {
      const confirmed = await onConfirmPlan();
      if (confirmed) {
        setReadyToStartConfirmedPlan(true);
      }
      return;
    }
    if (!readyToStartConfirmedPlan) {
      setReadyToStartConfirmedPlan(true);
      return;
    }
    setReadyToStartConfirmedPlan(false);
    await onStart();
  }

  return (
    <div className="space-y-4">
      <TaskSection title="环境">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoRow label="所属项目" value={displayValue(run?.project_name)} />
          <InfoRow label="探索环境" value={displayValue(run?.environment_name)} />
          <InfoRow label="登录策略" value={loginStrategy} />
          <InfoRow label="站点地址" value={displayValue(run?.environment_site_url)} />
        </div>
      </TaskSection>

      <TaskSection title="探索">
        <InfoRow label="任务名称" value={displayValue(run?.title)} />
        <InfoRow label="探索范围" value={displayValue(run?.scope)} />
        <InfoRow label="禁止路径" value={displayValue(run?.forbidden_paths)} />
        <InfoRow label="探索目标" value={displayValue(run?.goal)} />
        <InfoRow label="备注" value={displayValue(run?.notes)} />
      </TaskSection>

      <TaskSection title="执行边界">
        <div className="grid gap-3 md:grid-cols-3">
          <InfoRow label="页面上限" value={run ? `${run.max_pages ?? 50} 页` : "-"} />
          <InfoRow label="操作上限" value={run ? `${run.max_actions ?? 1000} 次` : "-"} />
          <InfoRow label="超时时间" value={run ? `${run.timeout_minutes ?? 120} 分钟` : "-"} />
        </div>
      </TaskSection>

      <TaskSection title="探索计划">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">计划状态</span>
              <Badge variant={planStatus === "confirmed" ? "default" : "secondary"}>{planStatusLabel}</Badge>
            </div>
            <p className="text-muted-foreground text-xs">
              {plan?.summary || "访问探索范围并由 AI 根据页面事实生成模块化探索计划。"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {editingPlan ? (
              <>
                <Button disabled={planAction === "save"} onClick={() => void savePlanDraft()} size="sm" type="button">
                  <Save className="size-4" />
                  {planAction === "save" ? "保存中" : "保存"}
                </Button>
                <Button
                  disabled={planAction === "save"}
                  onClick={() => {
                    setPlanDraft(formatPlanItemsDraft(plan?.items ?? []));
                    setPlanDraftError("");
                    setEditingPlan(false);
                  }}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <X className="size-4" />
                  取消
                </Button>
              </>
            ) : (
              <>
                {canStartFirstDiscovery ? (
                  <Button disabled={starting} onClick={() => void onStart()} size="sm" type="button" variant="outline">
                    <Play className="size-4" />
                    首次探索采集
                  </Button>
                ) : null}
                <Button
                  disabled={generatingPlan || !canGenerateDiscoveryPlan}
                  onClick={() => void onGeneratePlan()}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  {generatingPlan ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                  {generatingPlan ? "生成中" : "生成探索计划"}
                </Button>
                <Button
                  disabled={!canEdit || Boolean(planAction)}
                  onClick={() => setImportDialogOpen(true)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <Download className="size-4" />
                  从需求导入
                </Button>
                <AiEditInput
                  disabled={!canEditPlanWithAi}
                  label="AI 修改当前计划"
                  loading={editingPlanWithAi}
                  onSubmit={editPlanWithAi}
                  placeholder="描述你希望如何修改当前探索计划..."
                  title="AI 修改探索计划"
                />
                <Button
                  disabled={!canEdit || !plan || Boolean(planAction)}
                  onClick={() => setEditingPlan(true)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <Pencil className="size-4" />
                  手动修改探索计划
                </Button>
                <Button
                  disabled={confirmAndStartDisabled}
                  onClick={() => void confirmPlanThenStart()}
                  size="sm"
                  type="button"
                >
                  <Play className="size-4" />
                  {confirmAndStartLabel}
                </Button>
              </>
            )}
          </div>
        </div>

        {generatingPlan ? (
          <div className="rounded-lg border border-dashed bg-muted/30 p-3 text-muted-foreground text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Loader2 className="size-4 animate-spin" />
              <span className="font-medium text-foreground">探索计划正在生成</span>
              {generatingPlanElapsed ? <span>已等待 {generatingPlanElapsed}</span> : null}
            </div>
          </div>
        ) : null}

        {editingPlan ? (
          <div className="space-y-2">
            <Textarea
              className="min-h-96 font-mono text-xs"
              onChange={(event) => {
                setPlanDraft(event.target.value);
                setPlanDraftError("");
              }}
              spellCheck={false}
              value={planDraft}
            />
            {planDraftError ? <p className="text-destructive text-xs">{planDraftError}</p> : null}
          </div>
        ) : plan?.items.length ? (
          <div className="space-y-3">
            {plan.items.map((item) => (
              <div className="rounded-lg border bg-background p-3" key={item.id}>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0 space-y-1">
                    <div className="font-medium">{item.title}</div>
                    <div className="text-muted-foreground text-xs">所属模块：{item.business_module}</div>
                  </div>
                </div>
                <div className="mt-3 space-y-3">
                  <PlanList title="探索内容" values={item.steps} />
                  <PlanList title="已发现入口" values={item.exploration_points} />
                </div>
              </div>
            ))}
          </div>
        ) : generatingPlan ? null : (
          <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground text-sm">
            暂无探索计划。请点击生成探索计划，由 AI 访问探索范围并分析模块。
          </div>
        )}
      </TaskSection>
    </div>
  );
}

function PlanList({ title, values }: { title: string; values?: string[] }) {
  const listValues = Array.isArray(values) ? values : [];
  return (
    <div className="space-y-1">
      <div className="font-medium text-xs">{title}</div>
      <ul className="space-y-1 text-muted-foreground text-xs">
        {listValues.length ? listValues.map((value) => <li key={value}>{value}</li>) : <li>未设置</li>}
      </ul>
    </div>
  );
}

function TaskSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">{children}</CardContent>
    </Card>
  );
}

function GoalValidationSection({ detail, run }: { detail: ExplorationRunDetail | null; run: ExplorationRun | null }) {
  const validation = detail?.goal_validation;
  const goal = validation?.goal || run?.goal || "";
  const status = validation?.status || (goal ? "pending" : "skipped");
  const summary = validation?.summary || (goal ? "目标验证尚未执行。" : "未设置探索目标。");
  const stats = validation?.stats ?? {};
  const statText = (key: string) => formatUnknownCount(stats[key]);
  const statusLabel = goalValidationStatusLabels[status] ?? status;
  const statusClassName =
    status === "passed"
      ? "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300"
      : status === "failed"
        ? "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300"
        : status === "partial"
          ? "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
          : "bg-muted text-muted-foreground";

  return (
    <ShellSection>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-sm">目标验证</h2>
          <p className="text-muted-foreground text-xs">区分页面采集完成和探索目标是否达成</p>
        </div>
        <span className={cn("rounded px-2 py-1 text-xs", statusClassName)}>{statusLabel}</span>
      </div>
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <InfoRow label="探索目标" value={displayValue(goal)} />
        <InfoRow label="验证结论" value={summary} />
        <InfoRow label="页面" value={statText("page_count")} />
        <InfoRow
          label="链接"
          value={`已验证 ${statText("link_checked_count")}/${statText("link_total_count")}，失败 ${statText("link_failed_count")}`}
        />
        <InfoRow
          label="按钮"
          value={`已验证 ${statText("button_checked_count")}/${statText("button_total_count")}，未验证 ${statText("button_unverified_count")}，失败 ${statText("button_failed_count")}`}
        />
        <InfoRow label="风险" value={`失败 ${statText("failed_count")}，未验证 ${statText("unverified_count")}`} />
      </div>
    </ShellSection>
  );
}

function ExplorationFailureNotice({ error, onClose }: { error: string; onClose: () => void }) {
  return (
    <div className="flex min-h-10 items-center gap-2 rounded-lg border border-destructive/35 bg-destructive/8 px-3 text-sm shadow-sm">
      <AlertTriangle className="size-4 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1 truncate text-destructive">
        探索任务加载失败：{error}，详细信息请查看“探索日志”。
      </div>
      <Button aria-label="关闭探索失败信息" onClick={onClose} size="icon-xs" type="button" variant="ghost">
        <X className="size-4" />
      </Button>
    </div>
  );
}

function NoArtifactNotice({ onOpenLog, run }: { onOpenLog: () => void; run: ExplorationRun }) {
  const isCancelled = run.status === "cancelled";
  const title = isCancelled ? "本次探索已中止，未生成探索产物" : "本次探索被阻塞，未生成探索产物";
  const stopReason =
    run.result_summary || "用户已停止探索；此前任务已无运行中的浏览器探索进程，已生成的日志会继续保留。";
  const description = isCancelled
    ? "此前任务已无运行中的浏览器探索进程；如需重新执行，请使用页面右上角的重新探索。"
    : run.result_summary || "当前探索需要人工处理后才能继续，请查看日志确认阻塞原因和证据。";

  return (
    <div className="rounded-lg border bg-muted/20 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="font-medium">{title}</div>
          {isCancelled ? (
            <div className="text-foreground">
              <span className="text-muted-foreground">中止原因：</span>
              {stopReason}
            </div>
          ) : null}
          <p className="text-muted-foreground">{description}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button onClick={onOpenLog} size="sm" type="button" variant="outline">
            查看日志
          </Button>
        </div>
      </div>
    </div>
  );
}

function UnsupportedArtifactNotice({
  onOpenLog,
  onRestart,
  reason,
  restarting,
}: {
  onOpenLog?: () => void;
  onRestart: () => Promise<void> | void;
  reason: string;
  restarting: boolean;
}) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-950 text-sm dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4 shrink-0" />
            历史探索产物不支持新版详情
          </div>
          <p className="text-amber-800 dark:text-amber-200">{reason || "历史产物格式不支持新版详情，请重新探索。"}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          {onOpenLog ? (
            <Button onClick={onOpenLog} size="sm" type="button" variant="outline">
              查看日志
            </Button>
          ) : null}
          <Button disabled={restarting} onClick={() => void onRestart()} size="sm" type="button">
            <Play className="size-4" />
            重新探索
          </Button>
        </div>
      </div>
    </div>
  );
}

function ExplorationLogPanel({
  initialError,
  initialLog,
  failureDetail,
  projectId,
  run,
  runId,
}: {
  initialError: string;
  initialLog: ExplorationLog | null;
  failureDetail: {
    error: string;
    projectId: string;
    requestPath: string;
    runId: string;
    failedAt: string;
  } | null;
  projectId: string;
  run: ExplorationRun | null;
  runId: string;
}) {
  const [category, setCategory] = useState<LogCategory>("all");
  const [level, setLevel] = useState<LogLevel>("all");
  const [pageFilter, setPageFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [draftKeyword, setDraftKeyword] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [log, setLog] = useState<ExplorationLog | null>(initialLog);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(initialError);
  const [selectedEntry, setSelectedEntry] = useState<ParsedLogEntry | null>(null);
  const entries = useMemo(() => logEntriesFromResponse(log), [log]);
  const fallbackMode = !log?.items && Boolean(log?.log_content);
  const pageOptions = useMemo(() => buildLogPageOptions(entries), [entries]);
  const hasPagedLogResponse = Array.isArray(log?.items);
  const localFilteredEntries = useMemo(
    () => (fallbackMode ? filterLogEntries(entries, { category, keyword, level, page: pageFilter }) : entries),
    [category, entries, fallbackMode, keyword, level, pageFilter],
  );
  const total = fallbackMode ? localFilteredEntries.length : (log?.total ?? 0);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), pageCount);
  const visiblePages = getVisiblePages(safePage, pageCount);
  const pagedEntries = fallbackMode
    ? localFilteredEntries.slice((safePage - 1) * pageSize, safePage * pageSize)
    : entries;

  useEffect(() => {
    setLog(initialLog);
    setError(initialError);
    setSelectedEntry(null);
  }, [initialError, initialLog]);

  const loadPagedLog = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (keyword.trim()) query.set("keyword", keyword.trim());
      if (category !== "all") query.set("type", category);
      if (level !== "all") query.set("level", level);
      if (pageFilter !== "all") query.set("page_ref", pageFilter);
      const data = await apiRequest<ExplorationLog>(`/projects/${projectId}/exploration-runs/${runId}/log?${query}`);
      setLog(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "探索日志加载失败");
    } finally {
      setLoading(false);
    }
  }, [category, keyword, level, page, pageFilter, pageSize, projectId, runId]);

  useEffect(() => {
    void loadPagedLog();
  }, [loadPagedLog]);

  function resetLogPage() {
    setPage(1);
    setSelectedEntry(null);
  }

  function submitKeywordSearch() {
    const nextKeyword = draftKeyword.trim();
    if (nextKeyword === keyword) {
      return;
    }
    setKeyword(nextKeyword);
    resetLogPage();
  }

  function clearKeywordSearch() {
    if (!keyword && !draftKeyword) {
      return;
    }
    setDraftKeyword("");
    setKeyword("");
    resetLogPage();
  }

  function goToPage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
    setSelectedEntry(null);
  }

  return (
    <ShellSection>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-sm">探索日志</h2>
          <p className="text-muted-foreground text-xs">按事件展示页面访问、动作、阻塞、关系和产物写入记录</p>
        </div>
        <Button disabled={loading} onClick={() => void loadPagedLog()} size="sm" type="button" variant="outline">
          <RefreshCw className="size-4" />
          刷新日志
        </Button>
      </div>

      {failureDetail ? (
        <div className="space-y-3 rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-sm">
          <div className="flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="size-4" />
            探索任务加载失败
          </div>
          <div className="grid gap-2">
            <InfoRow label="失败原因" value={failureDetail.error} />
            <InfoRow label="项目 ID" value={failureDetail.projectId} />
            <InfoRow label="请求接口" value={failureDetail.requestPath} />
            <InfoRow label="失败时间" value={failureDetail.failedAt} />
            <InfoRow label="建议操作" value="检查后端服务、网络连接和当前账号权限后点击刷新重试。" />
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-destructive text-sm">
          探索日志加载失败：{error}
        </div>
      ) : entries.length > 0 || loading || hasPagedLogResponse ? (
        <div className="space-y-4">
          <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
              <div className="relative sm:w-72">
                <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pr-16 pl-8"
                  onChange={(event) => setDraftKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      submitKeywordSearch();
                    }
                  }}
                  placeholder="搜索页面、摘要或错误原因"
                  value={draftKeyword}
                />
                {draftKeyword ? (
                  <button
                    aria-label="清空搜索词"
                    className="absolute top-1/2 right-1 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground outline-none transition-none hover:bg-transparent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                    onClick={clearKeywordSearch}
                    type="button"
                  >
                    <X className="size-4" />
                  </button>
                ) : null}
              </div>
              <Button onClick={submitKeywordSearch} type="button" variant="outline">
                <Search className="size-4" />
                搜索
              </Button>
              <NativeSelect
                aria-label="事件类型"
                onChange={(event) => {
                  setCategory(event.target.value as LogCategory);
                  resetLogPage();
                }}
                value={category}
              >
                {logCategoryOptions.map((option) => (
                  <NativeSelectOption key={option} value={option}>
                    {logCategoryLabels[option]}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
              <NativeSelect
                aria-label="级别"
                onChange={(event) => {
                  setLevel(event.target.value as LogLevel);
                  resetLogPage();
                }}
                value={level}
              >
                {logLevelOptions.map((option) => (
                  <NativeSelectOption key={option} value={option}>
                    {logLevelLabels[option]}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
              <NativeSelect
                aria-label="页面"
                onChange={(event) => {
                  setPageFilter(event.target.value);
                  resetLogPage();
                }}
                value={pageFilter}
              >
                <NativeSelectOption value="all">全部页面</NativeSelectOption>
                {pageOptions.map((option) => (
                  <NativeSelectOption key={option.value} value={option.value}>
                    {option.label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border">
            <Table className="table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[15%]">时间</TableHead>
                  <TableHead className="w-[10%]">类型</TableHead>
                  <TableHead className="w-[26%]">页面</TableHead>
                  <TableHead className="w-[10%]">级别</TableHead>
                  <TableHead className="w-[33%]">摘要</TableHead>
                  <TableHead className="w-[6%]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                      探索日志加载中
                    </TableCell>
                  </TableRow>
                ) : (
                  pagedEntries.map((entry) => (
                    <LogEntryRows entry={entry} key={entry.id} onOpen={() => setSelectedEntry(entry)} />
                  ))
                )}
                {!loading && total === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                      没有符合筛选条件的日志。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>

          <LogPagination
            goToPage={goToPage}
            pageCount={pageCount}
            pageSize={pageSize}
            safePage={safePage}
            setPage={setPage}
            setPageSize={setPageSize}
            total={total}
            visiblePages={visiblePages}
          />
          <Dialog onOpenChange={(open) => !open && setSelectedEntry(null)} open={Boolean(selectedEntry)}>
            <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-5xl">
              <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
                <DialogTitle>日志详情</DialogTitle>
                <DialogDescription>
                  {selectedEntry ? `${selectedEntry.typeLabel} / ${selectedEntry.summary}` : "加载中"}
                </DialogDescription>
              </DialogHeader>
              <div className="min-h-0 overflow-auto px-6 pb-6">
                {selectedEntry ? <LogEntryDetail entry={selectedEntry} /> : null}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      ) : log?.log_content ? (
        <div className="rounded-lg border bg-background p-4">
          <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-6">{log.log_content}</pre>
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
          暂无失败日志。
          {run?.result_summary ? `最近执行摘要：${run.result_summary}` : "任务执行后会在这里展示日志信息。"}
        </div>
      )}
    </ShellSection>
  );
}

function ExplorationReportPanel({
  error,
  loading,
  onRestart,
  report,
  restarting,
}: {
  error: string;
  loading: boolean;
  onRestart: () => Promise<void> | void;
  report: ExplorationReport | null;
  restarting: boolean;
}) {
  const unsupportedReason = report?.unsupported_reason || "历史产物格式不支持新版报告，请重新探索。";

  return (
    <ShellSection>
      <div className="mb-4">
        <h2 className="font-medium text-sm">探索报告</h2>
      </div>

      {loading ? (
        <div className="py-10 text-center text-muted-foreground text-sm">探索报告加载中</div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-destructive text-sm">
          探索报告加载失败：{error}
        </div>
      ) : report?.unsupported_artifact ? (
        <UnsupportedArtifactNotice onRestart={onRestart} reason={unsupportedReason} restarting={restarting} />
      ) : report?.markdown_content ? (
        <div className="space-y-3">
          <div className="grid gap-2 rounded-lg border bg-muted/20 p-3 text-sm sm:grid-cols-2">
            <InfoRow label="报告版本" value={report.version_no ? `v${report.version_no}` : "-"} />
            <InfoRow label="生成时间" value={report.created_at ? formatDateTime(report.created_at) : "-"} />
          </div>
          <MarkdownPreview
            className="rounded-lg border bg-background p-4"
            content={report.markdown_content}
            emptyText="当前探索报告暂无可展示内容。"
          />
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
          暂无探索报告。探索任务完成后会在这里展示 Markdown 格式报告。
        </div>
      )}
    </ShellSection>
  );
}

function LogEntryRows({ entry, onOpen }: { entry: ParsedLogEntry; onOpen: () => void }) {
  const pageLabel = formatLogPageLabel(entry);
  const summary = formatLogSummary(entry);
  return (
    <TableRow>
      <TableCell className="truncate text-muted-foreground text-xs">{entry.timestamp || "-"}</TableCell>
      <TableCell>{entry.typeLabel}</TableCell>
      <TableCell className="truncate" title={pageLabel}>
        {pageLabel}
      </TableCell>
      <TableCell>
        <Badge variant={entry.level === "error" ? "destructive" : "outline"}>{logLevelLabels[entry.level]}</Badge>
      </TableCell>
      <TableCell className="truncate" title={summary}>
        {summary}
      </TableCell>
      <TableCell>
        <Button aria-label="查看日志详情" onClick={onOpen} size="icon-sm" variant="ghost">
          <Eye className="size-4" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

function formatLogPageLabel(entry: ParsedLogEntry): string {
  if (entry.pageTitle) return entry.pageTitle;
  if (entry.sourceLabel && entry.sourceLabel !== entry.pageId) return entry.sourceLabel;
  if (entry.url && !entry.url.startsWith("page-")) return entry.url;
  return entry.pageId || "-";
}

function formatLogSummary(entry: ParsedLogEntry): string {
  if (entry.type === "edge_created") {
    const relation = edgeRelationLabel(entry.result);
    const source = entry.sourceLabel || entry.pageTitle || entry.pageId || "-";
    const target = entry.targetLabel || entry.url || entry.result || "-";
    return `${relation}：${source} -> ${target}`;
  }
  return entry.summary;
}

function edgeRelationLabel(value: string): string {
  if (value === "navigation") return "同域链接";
  if (value === "external_link") return "外部链接";
  if (value === "form_submit") return "表单动作";
  if (value === "button_click") return "页面动作";
  return value || "页面关系";
}

function LogEntryDetail({ entry }: { entry: ParsedLogEntry }) {
  const payloadJson = Object.keys(entry.payload).length > 0 ? JSON.stringify(entry.payload, null, 2) : "";

  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <h3 className="font-medium text-muted-foreground text-xs">上下文</h3>
          <InfoRow label="页面 ID" value={entry.pageId || "-"} />
          <InfoRow label="页面标题" value={entry.pageTitle || "-"} />
          <InfoRow label="URL" value={entry.url || "-"} />
        </div>
        <div className="space-y-2">
          <h3 className="font-medium text-muted-foreground text-xs">动作与结果</h3>
          <InfoRow label="动作" value={entry.actionName || "-"} />
          <InfoRow label="结果" value={entry.result || "-"} />
          <InfoRow label="产物" value={entry.artifactPath || "-"} />
        </div>
      </div>
      {payloadJson ? (
        <div className="mt-4 space-y-2">
          <h3 className="font-medium text-muted-foreground text-xs">结构化字段</h3>
          <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-background p-3 font-mono text-[12px] leading-5">
            {payloadJson}
          </pre>
        </div>
      ) : null}
    </div>
  );
}

function LogPagination({
  goToPage,
  pageCount,
  pageSize,
  safePage,
  setPage,
  setPageSize,
  total,
  visiblePages,
}: {
  goToPage: (nextPage: number) => void;
  pageCount: number;
  pageSize: number;
  safePage: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
  setPageSize: React.Dispatch<React.SetStateAction<number>>;
  total: number;
  visiblePages: PageItem[];
}) {
  return (
    <div className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-end">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Pagination className="mx-0 w-auto justify-start sm:justify-end">
          <PaginationContent>
            <PaginationItem className="mr-2 text-muted-foreground">共 {total} 条数据</PaginationItem>
            <PaginationItem>
              <PaginationButton
                disabled={safePage <= 1}
                onClick={() => goToPage(safePage - 1)}
                type="button"
                variant="ghost"
              >
                <ChevronLeft className="rtl:rotate-180" /> 上一页
              </PaginationButton>
            </PaginationItem>
            {visiblePages.map((item) =>
              typeof item === "number" ? (
                <PaginationItem key={item}>
                  <PaginationButton
                    aria-current={item === safePage ? "page" : undefined}
                    mode="icon"
                    onClick={() => goToPage(item)}
                    selected={item === safePage}
                    type="button"
                    variant={item === safePage ? "outline" : "ghost"}
                  >
                    {item}
                  </PaginationButton>
                </PaginationItem>
              ) : (
                <PaginationItem key={item}>
                  <PaginationEllipsis />
                </PaginationItem>
              ),
            )}
            <PaginationItem>
              <PaginationButton
                disabled={safePage >= pageCount}
                onClick={() => goToPage(safePage + 1)}
                type="button"
                variant="ghost"
              >
                下一页 <ChevronRight className="rtl:rotate-180" />
              </PaginationButton>
            </PaginationItem>
          </PaginationContent>
        </Pagination>
        <label className="flex items-center gap-1 text-muted-foreground">
          <span>每页</span>
          <select
            aria-label="每页显示条数"
            className="h-8 rounded-md border border-input bg-background px-2 text-foreground text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
            value={pageSize}
          >
            {[10, 15, 20, 50, 100].map((option) => (
              <option key={option} value={option}>
                {option} 条
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

function parseLogEntries(content: string): ParsedLogEntry[] {
  const lines = content.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const entries: ParsedLogEntry[] = [];
  const timePrefixPattern =
    /^(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)?|\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)(?:\s*[|:-]\s*|\s+)(.*)$/;

  for (const line of lines) {
    const jsonEntry = parseJsonLogLine(line, entries.length);
    if (jsonEntry) {
      entries.push(jsonEntry);
      continue;
    }

    const matched = line.match(timePrefixPattern);
    if (matched) {
      entries.push(createRawLogEntry(entries.length, line, matched[1], matched[2]?.trim() || line.trim()));
      continue;
    }

    const lastEntry = entries.at(-1);
    if (lastEntry?.type === "raw") {
      lastEntry.raw = `${lastEntry.raw}\n${line}`;
      lastEntry.summary = `${lastEntry.summary}\n${line}`;
    } else {
      entries.push(createRawLogEntry(entries.length, line, "", line.trim()));
    }
  }

  return entries;
}

function logEntriesFromResponse(log: ExplorationLog | null): ParsedLogEntry[] {
  if (!log) {
    return [];
  }
  if (Array.isArray(log.items)) {
    return log.items.map((item) => ({
      actionName: item.action_name,
      artifactPath: item.artifact_path,
      category: normalizeLogCategory(item.category),
      id: item.id,
      level: normalizeLogLevel(item.level),
      pageId: item.page_id,
      pageTitle: item.page_title,
      payload: item.payload ?? {},
      raw: item.raw,
      result: item.result,
      sourceLabel: item.source_label ?? "",
      summary: item.summary,
      targetLabel: item.target_label ?? "",
      timestamp: item.timestamp,
      type: item.event,
      typeLabel: item.event_label || item.event,
      url: item.url,
    }));
  }
  return parseLogEntries(log.log_content ?? "");
}

function normalizeLogCategory(value: string): LogCategory {
  return logCategoryOptions.includes(value as LogCategory) ? (value as LogCategory) : "raw";
}

function normalizeLogLevel(value: string): LogLevel {
  return logLevelOptions.includes(value as LogLevel) ? (value as LogLevel) : "info";
}

function parseJsonLogLine(line: string, index: number): ParsedLogEntry | null {
  try {
    const parsed = JSON.parse(line) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }

    const event = stringValue(parsed.event) || "raw";
    const level = inferLogLevel(event, parsed);
    const pageId = firstString(parsed, ["page_id", "page", "source"]);
    const pageTitle = firstString(parsed, ["page_title", "title"]);
    const url = firstString(parsed, ["url", "target"]);
    const actionName = firstString(parsed, ["action", "name", "locator_hint"]);
    const result = firstString(parsed, ["status", "reason", "type", "target", "edge_id"]);
    const artifactPath = firstString(parsed, ["artifact_path", "evidence_path", "file_path", "log_path"]);

    return {
      actionName,
      artifactPath,
      category: inferLogCategory(event),
      id: `log-${index}`,
      level,
      pageId,
      pageTitle,
      payload: parsed,
      raw: line,
      result,
      summary: buildLogEntrySummary(event, parsed),
      sourceLabel: "",
      targetLabel: "",
      timestamp: formatLogTimestamp(firstString(parsed, ["ts", "time", "timestamp"])),
      type: event,
      typeLabel: logTypeLabels[event] ?? event,
      url,
    };
  } catch {
    return null;
  }
}

function createRawLogEntry(index: number, raw: string, timestamp: string, summary: string): ParsedLogEntry {
  const level = /error|traceback|typeerror|exception|failed|失败/i.test(raw) ? "error" : "info";
  return {
    actionName: "",
    artifactPath: "",
    category: level === "error" ? "error" : "raw",
    id: `log-${index}`,
    level,
    pageId: "",
    pageTitle: "",
    payload: {},
    raw,
    result: "",
    sourceLabel: "",
    summary,
    targetLabel: "",
    timestamp,
    type: "raw",
    typeLabel: logTypeLabels.raw,
    url: "",
  };
}

function inferLogCategory(event: string): LogCategory {
  if (event === "blocked") return "blocked";
  if (event === "error") return "error";
  if (
    event.includes("page") ||
    event === "accessibility_captured" ||
    event === "agent_observed" ||
    event === "observe"
  ) {
    return "page";
  }
  if (
    event.includes("action") ||
    event.includes("edge") ||
    event === "agent_decision" ||
    event === "agent_decision_fallback"
  ) {
    return "action";
  }
  if (event.includes("artifact")) return "artifact";
  if (event.includes("run") || event.includes("login") || event === "skipped") return "run";
  return "raw";
}

function inferLogLevel(event: string, payload: Record<string, unknown>): LogLevel {
  const explicit = stringValue(payload.level).toLowerCase();
  if (explicit === "error" || explicit === "warning" || explicit === "info") return explicit;
  if (event === "error" || stringValue(payload.status) === "failed") return "error";
  if (event === "blocked" || event === "skipped") {
    return "warning";
  }
  return "info";
}

function buildLogEntrySummary(event: string, payload: Record<string, unknown>): string {
  if (event === "run_started") {
    return `开始探索 ${firstString(payload, ["url"]) || "目标站点"}`;
  }
  if (event === "run_completed") {
    return `探索完成，状态 ${firstString(payload, ["status"]) || "completed"}`;
  }
  if (
    event === "page_captured" ||
    event === "page_visited" ||
    event === "page_discovered" ||
    event === "agent_observed" ||
    event === "observe"
  ) {
    return `采集页面 ${firstString(payload, ["title", "page_id", "url"]) || "-"}`;
  }
  if (event === "edge_created") {
    return `记录关系 ${firstString(payload, ["edge_id"]) || ""}：${firstString(payload, ["source"]) || "-"} -> ${firstString(payload, ["target"]) || "-"}`;
  }
  if (event === "agent_decision") {
    return `Agent 决策 ${firstString(payload, ["decision_type"]) || "-"}：${firstString(payload, ["action", "action_type"]) || "-"}`;
  }
  if (event === "agent_decision_fallback") {
    return `Agent 决策降级：${firstString(payload, ["reason"]) || "-"}`;
  }
  if (event === "action_executed") {
    return `执行动作 ${firstString(payload, ["action", "name", "locator_hint"]) || "-"}`;
  }
  if (event === "action_started" || event === "action_result" || event === "action_completed") {
    return `动作 ${firstString(payload, ["action", "action_type"]) || "-"}：${firstString(payload, ["status", "target"]) || "-"}`;
  }
  if (event === "blocked" || event === "skipped") {
    return firstString(payload, ["reason", "action", "page_id", "page"]) || logTypeLabels[event] || event;
  }
  if (event === "artifact_written") {
    return `写入产物 ${firstString(payload, ["artifact_path", "file_path"]) || "-"}`;
  }
  if (event === "error") {
    return firstString(payload, ["message", "reason", "error"]) || "探索执行错误";
  }
  return (
    firstString(payload, ["summary", "recent_event", "message", "url", "page_id"]) || logTypeLabels[event] || event
  );
}

function buildLogPageOptions(entries: ParsedLogEntry[]) {
  const pages = new Map<string, string>();
  for (const entry of entries) {
    const value = entry.pageId || entry.pageTitle || entry.url;
    if (!value) continue;
    pages.set(value, entry.pageTitle || entry.pageId || entry.url);
  }
  return Array.from(pages, ([value, label]) => ({ label, value }));
}

function filterLogEntries(
  entries: ParsedLogEntry[],
  filters: { category: LogCategory; keyword: string; level: LogLevel; page: string },
) {
  const keyword = filters.keyword.trim().toLowerCase();
  return entries.filter((entry) => {
    if (filters.category !== "all" && entry.category !== filters.category) return false;
    if (filters.level !== "all" && entry.level !== filters.level) return false;
    if (filters.page !== "all" && ![entry.pageId, entry.pageTitle, entry.url].includes(filters.page)) return false;
    if (!keyword) return true;
    return [
      entry.summary,
      entry.raw,
      entry.url,
      entry.pageTitle,
      entry.pageId,
      entry.actionName,
      entry.result,
      entry.artifactPath,
    ]
      .join("\n")
      .toLowerCase()
      .includes(keyword);
  });
}

function firstString(payload: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = stringValue(payload[key]);
    if (value) return value;
  }
  return "";
}

function stringValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function formatLogTimestamp(value: string): string {
  if (!value) return "";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(parsed);
}

function formatExplorationDuration(run: ExplorationRun, now: number = Date.now()): string {
  if (!run.started_at) {
    return "-";
  }

  const startedAt = parseApiTimestamp(run.started_at);
  const finishedAt = run.finished_at ? parseApiTimestamp(run.finished_at) : now;
  if (!Number.isFinite(startedAt) || !Number.isFinite(finishedAt) || finishedAt < startedAt) {
    return "-";
  }

  const totalSeconds = Math.floor((finishedAt - startedAt) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function formatElapsedDuration(durationMs: number): string {
  const totalSeconds = Math.max(0, Math.floor(durationMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes <= 0) {
    return `${seconds} 秒`;
  }

  return `${minutes} 分 ${String(seconds).padStart(2, "0")} 秒`;
}

function hasNoModuleArtifacts(module: ExplorationRunDetail["modules"][number]): boolean {
  return module.pages.length === 0 && module.elements.length === 0 && module.blockers.length === 0;
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[96px_1fr]">
      <div className="text-muted-foreground">{label}</div>
      <div className="min-w-0 break-words font-medium">{value}</div>
    </div>
  );
}

function displayValue(value: string | null | undefined): string {
  return value?.trim() || "-";
}

function formatUnknownCount(value: unknown): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "0";
}

function TimelineItem({ active, label, value }: { active: boolean; label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div
          className={active ? "mt-1 size-2 rounded-full bg-primary" : "mt-1 size-2 rounded-full bg-muted-foreground/30"}
        />
        <div className="mt-1 h-8 w-px bg-border" />
      </div>
      <div className="min-w-0">
        <div className="font-medium">{label}</div>
        <div className="text-muted-foreground text-xs">{value}</div>
      </div>
    </div>
  );
}

type RequirementDocument = {
  id: string;
  title: string;
  status: string;
  created_at: string;
};

type RequirementAnalysisRun = {
  id: string;
  status: string;
  created_at: string;
  has_enhanced_requirement: boolean;
};

function RequirementImportDialog({
  importingFromRequirement,
  onImport,
  onOpenChange,
  open,
  projectId,
}: {
  importingFromRequirement: boolean;
  onImport: (requirementDocId: string, requirementRunId: string) => Promise<void>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  projectId: string;
}) {
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<RequirementDocument[]>([]);
  const [selectedDocId, setSelectedDocId] = useState("");
  const [analysisRuns, setAnalysisRuns] = useState<RequirementAnalysisRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [loadingRuns, setLoadingRuns] = useState(false);

  useEffect(() => {
    if (open) {
      loadDocuments();
    } else {
      setSelectedDocId("");
      setSelectedRunId("");
      setAnalysisRuns([]);
    }
  }, [open]);

  useEffect(() => {
    if (selectedDocId) {
      loadAnalysisRuns(selectedDocId);
    } else {
      setAnalysisRuns([]);
      setSelectedRunId("");
    }
  }, [selectedDocId]);

  async function loadDocuments() {
    setLoading(true);
    try {
      const docs = await apiRequest<RequirementDocument[]>(`/projects/${projectId}/requirements`);
      setDocuments(docs);
    } catch (error) {
      toast.error("加载需求文档列表失败");
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  async function loadAnalysisRuns(docId: string) {
    setLoadingRuns(true);
    setSelectedRunId("");
    try {
      const runs = await apiRequest<RequirementAnalysisRun[]>(
        `/projects/${projectId}/requirements/${docId}/analysis-runs`
      );
      // 只显示已完成且有增强版需求的分析运行
      const validRuns = runs.filter((run) => run.status === "completed" && run.has_enhanced_requirement);
      setAnalysisRuns(validRuns);
      if (validRuns.length === 1) {
        setSelectedRunId(validRuns[0].id);
      }
    } catch (error) {
      toast.error("加载需求分析记录失败");
      console.error(error);
    } finally {
      setLoadingRuns(false);
    }
  }

  async function handleImport() {
    if (!selectedDocId || !selectedRunId) {
      toast.error("请选择需求文档和分析记录");
      return;
    }
    await onImport(selectedDocId, selectedRunId);
  }

  const canImport = !importingFromRequirement && selectedDocId && selectedRunId;

  return (
    <Dialog onOpenChange={onOpenChange} open={open}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>从需求导入探索计划</DialogTitle>
          <DialogDescription>选择已完成分析的需求文档，将自动生成探索计划并导入到当前任务。</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="requirement-doc-select">
              需求文档
            </label>
            {loading ? (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin" />
                加载中...
              </div>
            ) : documents.length === 0 ? (
              <p className="text-muted-foreground text-sm">当前项目没有需求文档</p>
            ) : (
              <Select onValueChange={setSelectedDocId} value={selectedDocId}>
                <SelectTrigger id="requirement-doc-select">
                  <SelectValue placeholder="选择需求文档" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {selectedDocId && (
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="analysis-run-select">
                需求分析记录
              </label>
              {loadingRuns ? (
                <div className="flex items-center gap-2 text-muted-foreground text-sm">
                  <Loader2 className="size-4 animate-spin" />
                  加载中...
                </div>
              ) : analysisRuns.length === 0 ? (
                <p className="text-muted-foreground text-sm">该需求文档没有已完成的分析记录</p>
              ) : (
                <Select onValueChange={setSelectedRunId} value={selectedRunId}>
                  <SelectTrigger id="analysis-run-select">
                    <SelectValue placeholder="选择分析记录" />
                  </SelectTrigger>
                  <SelectContent>
                    {analysisRuns.map((run) => (
                      <SelectItem key={run.id} value={run.id}>
                        {formatDateTime(parseApiTimestamp(run.created_at))}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button disabled={importingFromRequirement} onClick={() => onOpenChange(false)} type="button" variant="outline">
            取消
          </Button>
          <Button disabled={!canImport} onClick={() => void handleImport()} type="button">
            {importingFromRequirement ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                导入中...
              </>
            ) : (
              "导入"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
      </div>
    </div>
  );
}
