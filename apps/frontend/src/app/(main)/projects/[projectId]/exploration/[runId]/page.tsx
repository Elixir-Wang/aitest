"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { useParams } from "next/navigation";

import {
  AlertTriangle,
  FileText,
  ListChecks,
  Pencil,
  Play,
  RefreshCw,
  Route,
  Square,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { AgentPlan, type AgentPlanStatus, type AgentPlanTask } from "@/components/ui/agent-plan";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
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
import { StatusBadge } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { API_BASE_URL, apiAuthHeaders, apiRequest, formatDateTime, parseApiTimestamp } from "@/lib/api-client";
import { reportError as reportApiError } from "@/lib/error-feedback";

type ExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  environment_site_url: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
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

type ExplorationStreamEvent = {
  event_id?: number;
  type: string;
  run_id: string;
  payload: Record<string, unknown> | ExplorationRunDetail;
};

type ExplorationMonitorPlanStep = {
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

type ExplorationMonitorStep = ExplorationMonitorPlanStep & {
  status: AgentPlanStatus;
  total_steps: number;
  attempt: number;
  started_at: string;
  completed_at: string;
  duration_ms: number | null;
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
  screenshot_path: string;
};

type ExplorationMonitorEvent = {
  id: string;
  type: string;
  label: string;
  summary: string;
  occurred_at: string;
  status: AgentPlanStatus;
};

type ExplorationMonitorState = {
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
  } | null;
  steps: ExplorationMonitorStep[];
  events: ExplorationMonitorEvent[];
};

type ExplorationEnvironment = {
  id: string;
  name: string;
};

type RequirementDocument = {
  id: string;
  name: string;
  status: string;
  current_version_id: string | null;
  created_at: string;
  latest_requirement_analysis_run?: {
    id: string;
    status: string;
  } | null;
};

function isExplorationLinkableRequirement(requirement: RequirementDocument) {
  return Boolean(requirement.current_version_id);
}

type ExplorationForm = {
  title: string;
  environmentId: string;
  requirementDocId: string;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};

type PageItem = { type: "page"; page: number; id: string } | { type: "ellipsis"; id: string };

const statusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  stopping: "正在停止",
  cancelled: "已中止",
  interrupted: "已中断",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const loginStrategyLabels: Record<string, string> = {
  account_password: "账号密码",
  skip_login: "无需登录",
};

const logTypeLabels: Record<string, string> = {
  run_started: "探索开始",
  planning_started: "规划开始",
  planning_completed: "规划完成",
  execution_started: "执行开始",
  execution_completed: "执行完成",
  exploration_cancelled: "探索取消",
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
  step_started: "步骤开始",
  step_completed: "步骤完成",
  step_failed: "步骤失败",
  step_skipped: "步骤跳过",
  step_retrying: "步骤重试",
  step_recorded: "探索步骤",
  direct_step_started: "直接执行开始",
  agentic_step_started: "智能执行开始",
  edge_created: "记录关系",
  artifact_written: "写入产物",
  blocked: "探索阻塞",
  skipped: "跳过",
  error: "错误",
  run_completed: "探索完成",
  raw: "原始日志",
};

const emptyMonitorState: ExplorationMonitorState = {
  phase: "idle",
  plan: null,
  steps: [],
  events: [],
};

const autoRefreshStatuses = new Set(["queued", "running", "stopping", "in-progress"]);
const stoppableStatuses = new Set(["queued", "running"]);
const explorationPlaceholders = {
  scope: "填写本次要探索的页面范围，例如全站、指定菜单、指定 URL 或核心模块。",
  forbiddenPaths: "填写禁止进入或点击的路径/动作，例如删除、支付、外发、批量通知、退出登录。",
  goal: "填写本次探索要验证的目标，例如遍历元素和链接，检查 401/403、登录跳转和异常页。",
};
const NO_REQUIREMENT_VALUE = "__none__";
const emptyExplorationForm: ExplorationForm = {
  title: "",
  environmentId: "",
  requirementDocId: "",
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
    return Array.from({ length: pageCount }, (_, index) => ({
      type: "page" as const,
      page: index + 1,
      id: `page-${index + 1}`,
    }));
  }

  const createPage = (page: number): PageItem => ({ type: "page" as const, page, id: `page-${page}` });
  const createEllipsis = (id: string): PageItem => ({ type: "ellipsis" as const, id });

  if (currentPage <= 4) {
    return [
      createPage(1),
      createPage(2),
      createPage(3),
      createPage(4),
      createPage(5),
      createEllipsis("ellipsis-end"),
      createPage(pageCount),
    ];
  }

  if (currentPage >= pageCount - 3) {
    return [
      createPage(1),
      createEllipsis("ellipsis-start"),
      createPage(pageCount - 4),
      createPage(pageCount - 3),
      createPage(pageCount - 2),
      createPage(pageCount - 1),
      createPage(pageCount),
    ];
  }

  return [
    createPage(1),
    createEllipsis("ellipsis-start"),
    createPage(currentPage - 1),
    createPage(currentPage),
    createPage(currentPage + 1),
    createEllipsis("ellipsis-end"),
    createPage(pageCount),
  ];
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
    setMonitor: React.Dispatch<React.SetStateAction<ExplorationMonitorState>>;
    setRun: React.Dispatch<React.SetStateAction<ExplorationRun | null>>;
  },
) {
  if (event.type === "run_snapshot") {
    const snapshot = normalizeExplorationRunDetail(event.payload as ExplorationRunDetail);
    setters.setRun(snapshot.run);
    setters.setStreamDetail(snapshot);
    setters.setMonitor(monitorFromRunDetail(snapshot));
    return;
  }

  setters.setMonitor((current) => mergeMonitorEvent(current, event));

  // 处理运行状态事件
  if (
    event.type === "run_started" ||
    event.type === "run_completed" ||
    event.type === "run_failed" ||
    event.type === "run_cancelled" ||
    event.type === "run_status_updated"
  ) {
    setters.setRun((current) => (current ? { ...current, ...(event.payload as Partial<ExplorationRun>) } : current));
    setters.setStreamDetail((current) =>
      current ? { ...current, run: { ...current.run, ...(event.payload as Partial<ExplorationRun>) } } : current,
    );
  }

  // 处理规划和执行阶段事件
  if (
    event.type === "planning_started" ||
    event.type === "planning_completed" ||
    event.type === "step_started" ||
    event.type === "step_completed" ||
    event.type === "step_failed" ||
    event.type === "step_skipped" ||
    event.type === "step_retrying" ||
    event.type === "re_planning_started" ||
    event.type === "re_planning_completed"
  ) {
    return;
  }

  // 处理模块事件
  if (event.type.startsWith("module_")) {
    setters.setStreamDetail((current) => mergeModuleEvent(current, event));
  }
  // 处理页面事件
  else if (event.type.startsWith("page_")) {
    setters.setStreamDetail((current) => mergePageEvent(current, event));
  }
  // 处理步骤事件
  else if (event.type === "step_recorded") {
    setters.setStreamDetail((current) => mergeStepEvent(current, event));
  }
  // 处理阻塞事件
  else if (event.type === "blocker_detected") {
    setters.setStreamDetail((current) => mergeBlockerEvent(current, event));
  }
}

function mergeMonitorEvent(current: ExplorationMonitorState, event: ExplorationStreamEvent): ExplorationMonitorState {
  if (event.type === "run_snapshot") {
    return monitorFromRunDetail(event.payload as ExplorationRunDetail);
  }
  const payload = event.payload as Record<string, unknown>;
  let next: ExplorationMonitorState = {
    ...current,
    phase: monitorPhaseFromEvent(event.type, current.phase),
  };

  if (event.type === "planning_completed") {
    const steps = normalizeMonitorPlanSteps(payload.steps);
    next = {
      ...next,
      plan: {
        plan_id: stringValue(payload.plan_id),
        goal_summary: stringValue(payload.goal_summary),
        scope_summary: stringValue(payload.scope_summary),
        strategy: stringValue(payload.strategy),
        modules: arrayOfStrings(payload.modules),
        estimated_duration_minutes: numberOrNull(payload.estimated_duration_minutes),
        risk_assessment: stringValue(payload.risk_assessment),
        success_criteria: arrayOfStrings(payload.success_criteria),
        total_steps: Number(payload.total_steps || steps.length || 0),
      },
      steps: mergeMonitorPlanSteps(next.steps, steps),
    };
  }

  if (isStepMonitorEvent(event.type)) {
    const incomingStep = monitorStepFromPayload(event.type, payload, current.plan?.total_steps ?? 0);
    if (incomingStep) {
      next = { ...next, steps: upsertMonitorStep(next.steps, incomingStep) };
    }
  }

  return {
    ...next,
    events: [monitorTimelineEvent(event), ...next.events].slice(0, 80),
  };
}

function monitorFromRunDetail(detail: ExplorationRunDetail): ExplorationMonitorState {
  const steps = monitorStepsFromDetail(detail);
  return {
    phase: monitorPhaseFromRunStatus(detail.run.status),
    plan: monitorPlanFromDetail(detail, steps),
    steps,
    events: monitorEventsFromDetail(detail, steps),
  };
}

function monitorStepsFromDetail(detail: ExplorationRunDetail): ExplorationMonitorStep[] {
  const steps: ExplorationMonitorStep[] = [];
  for (const module of detail.modules) {
    for (const page of module.pages) {
      for (const step of page.steps ?? []) {
        const planStep = monitorPlanStepFromDetailStep(step, module.module_name, steps.length + 1);
        steps.push({
          ...emptyMonitorStep(planStep),
          status: normalizeAgentPlanStatus(step.status || page.status || module.completion_status),
          completed_at: step.occurred_at || "",
          message: step.detail || "",
        });
      }
    }
  }
  return steps;
}

function monitorPlanStepFromDetailStep(
  step: ExplorationStep,
  moduleName: string,
  fallbackIndex: number,
): ExplorationMonitorPlanStep {
  return {
    step_id: step.id || `snapshot-step-${String(fallbackIndex).padStart(3, "0")}`,
    step_number: fallbackIndex,
    module_name: moduleName,
    action_type: step.type || "event",
    description: step.title || "探索步骤",
    target_description: step.detail ?? step.title ?? "",
    target_selector: "",
    value: "",
    expected_result: step.detail ?? "",
    execution_strategy: step.source === "exploration_plan" ? "planned" : "observed",
    is_critical: false,
    retry_on_failure: false,
    max_retries: 0,
  };
}

function monitorPlanFromDetail(
  detail: ExplorationRunDetail,
  steps: ExplorationMonitorStep[],
): ExplorationMonitorState["plan"] {
  if (!steps.length && !isActiveStatus(detail.run.status)) {
    return null;
  }
  return {
    plan_id: "",
    goal_summary: detail.run.goal,
    scope_summary: detail.run.scope,
    strategy: "目标驱动探索",
    modules: detail.modules.map((module) => module.module_name).filter(Boolean),
    estimated_duration_minutes: detail.run.timeout_minutes,
    risk_assessment: detail.run.forbidden_paths ? `禁止路径：${detail.run.forbidden_paths}` : "",
    success_criteria: detail.run.goal ? [detail.run.goal] : [],
    total_steps: steps.length,
  };
}

function monitorEventsFromDetail(
  detail: ExplorationRunDetail,
  steps: ExplorationMonitorStep[],
): ExplorationMonitorEvent[] {
  const events = steps
    .filter((step) => step.message || step.status !== "pending")
    .slice(-20)
    .reverse()
    .map((step) => ({
      id: `snapshot-${step.step_id}`,
      type: "run_snapshot",
      label: "当前步骤",
      summary: step.message || step.description,
      occurred_at: step.completed_at || detail.run.updated_at,
      status: step.status,
    }));
  if (detail.run.result_summary) {
    events.unshift({
      id: "snapshot-run-summary",
      type: "run_snapshot",
      label: "当前状态",
      summary: detail.run.result_summary,
      occurred_at: detail.run.updated_at,
      status: normalizeAgentPlanStatus(detail.run.status),
    });
  }
  return events;
}

function monitorPhaseFromRunStatus(status: string): string {
  if (status === "queued") return "planning";
  if (status === "running" || status === "stopping") return "executing";
  if (status === "completed" || status === "partial") return "completed";
  if (status === "blocked" || status === "failed" || status === "interrupted") return "failed";
  if (status === "cancelled") return "cancelled";
  return "idle";
}

function monitorPhaseFromEvent(eventType: string, currentPhase: string): string {
  if (eventType === "planning_started") return "planning";
  if (eventType === "planning_completed") return "planned";
  if (eventType === "execution_started" || eventType === "step_started") return "executing";
  if (eventType === "re_planning_started") return "replanning";
  if (eventType === "run_completed") return "completed";
  if (eventType === "run_failed" || eventType === "error") return "failed";
  if (eventType === "run_cancelled" || eventType === "exploration_cancelled") return "cancelled";
  return currentPhase;
}

function isStepMonitorEvent(eventType: string): boolean {
  return ["step_started", "step_completed", "step_failed", "step_skipped", "step_retrying"].includes(eventType);
}

function normalizeMonitorPlanSteps(value: unknown): ExplorationMonitorPlanStep[] {
  if (!Array.isArray(value)) return [];
  return value.map((item, index) => monitorPlanStepFromPayload(item, index + 1)).filter(Boolean);
}

function monitorPlanStepFromPayload(value: unknown, fallbackIndex: number): ExplorationMonitorPlanStep {
  const item = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    step_id: stringValue(item.step_id || `step-${String(fallbackIndex).padStart(3, "0")}`),
    step_number: Number(item.step_number || fallbackIndex),
    module_name: stringValue(item.module_name),
    action_type: stringValue(item.action_type || "event"),
    description: stringValue(item.description || "探索步骤"),
    target_description: stringValue(item.target_description),
    target_selector: stringValue(item.target_selector),
    value: stringValue(item.value),
    expected_result: stringValue(item.expected_result),
    execution_strategy: stringValue(item.execution_strategy || "direct"),
    is_critical: Boolean(item.is_critical),
    retry_on_failure: item.retry_on_failure !== false,
    max_retries: Number(item.max_retries || 0),
  };
}

function mergeMonitorPlanSteps(
  currentSteps: ExplorationMonitorStep[],
  planSteps: ExplorationMonitorPlanStep[],
): ExplorationMonitorStep[] {
  return planSteps.map((planStep) => {
    const existing = currentSteps.find((step) => step.step_id === planStep.step_id);
    return {
      ...emptyMonitorStep(planStep),
      ...existing,
      ...planStep,
    };
  });
}

function monitorStepFromPayload(
  eventType: string,
  payload: Record<string, unknown>,
  fallbackTotalSteps: number,
): ExplorationMonitorStep | null {
  const planStep = monitorPlanStepFromPayload(payload, Number(payload.step_number || 1));
  if (!planStep.step_id) return null;
  return {
    ...emptyMonitorStep(planStep),
    status: monitorStepStatusFromEvent(eventType),
    total_steps: Number(payload.total_steps || fallbackTotalSteps || 0),
    attempt: Number(payload.attempt || 1),
    started_at: stringValue(payload.started_at),
    completed_at: stringValue(payload.completed_at),
    duration_ms: numberOrNull(payload.duration_ms),
    success: typeof payload.success === "boolean" ? payload.success : null,
    message: stringValue(payload.message),
    error: stringValue(payload.error || payload.reason || payload.previous_error),
    failure_type: stringValue(payload.failure_type),
    retryable: Boolean(payload.retryable),
    matched_element: monitorMatchedElement(payload.matched_element),
    page_state: monitorPageState(payload.page_state),
    screenshot_path: stringValue(payload.screenshot_path),
  };
}

function emptyMonitorStep(planStep: ExplorationMonitorPlanStep): ExplorationMonitorStep {
  return {
    ...planStep,
    status: "pending",
    total_steps: 0,
    attempt: 0,
    started_at: "",
    completed_at: "",
    duration_ms: null,
    success: null,
    message: "",
    error: "",
    failure_type: "",
    retryable: false,
    matched_element: { id: "", role: "", name: "", selector: "" },
    page_state: { url: "", title: "", element_count: 0 },
    screenshot_path: "",
  };
}

function upsertMonitorStep(steps: ExplorationMonitorStep[], incoming: ExplorationMonitorStep): ExplorationMonitorStep[] {
  const existingIndex = steps.findIndex((step) => step.step_id === incoming.step_id);
  if (existingIndex < 0) {
    return [...steps, incoming].sort((a, b) => a.step_number - b.step_number);
  }
  return steps.map((step, index) => (index === existingIndex ? { ...step, ...incoming } : step));
}

function monitorStepStatusFromEvent(eventType: string): AgentPlanStatus {
  if (eventType === "step_started" || eventType === "step_retrying") return "running";
  if (eventType === "step_completed") return "completed";
  if (eventType === "step_failed") return "failed";
  if (eventType === "step_skipped") return "partial";
  return "pending";
}

function monitorMatchedElement(value: unknown): ExplorationMonitorStep["matched_element"] {
  const item = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    id: stringValue(item.id),
    role: stringValue(item.role),
    name: stringValue(item.name),
    selector: stringValue(item.selector),
  };
}

function monitorPageState(value: unknown): ExplorationMonitorStep["page_state"] {
  const item = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    url: stringValue(item.url),
    title: stringValue(item.title),
    element_count: Number(item.element_count || 0),
  };
}

function monitorTimelineEvent(event: ExplorationStreamEvent): ExplorationMonitorEvent {
  const payload = event.payload as Record<string, unknown>;
  const stepNumber = payload.step_number ? `#${payload.step_number} ` : "";
  const summary =
    stringValue(payload.message) ||
    stringValue(payload.error) ||
    stringValue(payload.description) ||
    stringValue(payload.reason) ||
    stringValue(payload.strategy);
  return {
    id: `${event.type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    type: event.type,
    label: logTypeLabels[event.type] ?? event.type,
    summary: `${stepNumber}${summary || "收到探索事件"}`,
    occurred_at: stringValue(payload.completed_at || payload.started_at || payload.occurred_at) || new Date().toISOString(),
    status: monitorTimelineStatus(event.type),
  };
}

function monitorTimelineStatus(eventType: string): AgentPlanStatus {
  if (eventType.includes("failed") || eventType === "error") return "failed";
  if (eventType.includes("completed")) return "completed";
  if (eventType.includes("cancelled")) return "cancelled";
  if (eventType.includes("started") || eventType === "step_retrying") return "running";
  return "pending";
}

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function numberOrNull(value: unknown): number | null {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
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
    completion_summary: String(payload.completion_summary || ""),
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
  const targetModuleIndex = findStreamModuleIndex(detail.modules, moduleId);
  if (targetModuleIndex < 0) {
    return detail;
  }
  const modules = detail.modules.map((module, moduleIndex) => {
    if (moduleIndex !== targetModuleIndex) {
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

function findStreamModuleIndex(modules: ExplorationRunDetail["modules"], moduleId: string): number {
  const exactIndex = modules.findIndex((module) => module.id === moduleId || module.module_key === moduleId);
  if (exactIndex >= 0) {
    return exactIndex;
  }
  return modules.length === 1 ? 0 : -1;
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
  const targetModuleIndex = findStreamModuleIndex(detail.modules, moduleId);
  if (targetModuleIndex < 0) {
    return detail;
  }
  const modules = detail.modules.map((module, moduleIndex) => {
    if (moduleIndex !== targetModuleIndex) {
      return module;
    }
    const existingPageIndex = module.pages.findIndex((page) => page.id === pageId);
    const sourcePages =
      existingPageIndex >= 0
        ? module.pages
        : [
            ...module.pages,
            {
              id: pageId,
              title: pageId,
              url: "",
              entry_path: "",
              yaml_path: "",
              status: "running",
              blocker_reason: "",
              recent_event: "",
              structure_summary: "",
              steps: [],
            },
          ];
    const pages = sourcePages.map((page) => {
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
      subtasks: buildModulePlanSubtasks(detail, module),
    }));
}

function buildModulePlanSubtasks(
  detail: ExplorationRunDetail,
  module: ExplorationRunDetail["modules"][number],
): NonNullable<AgentPlanTask["subtasks"]> {
  if (module.pages.length > 0) {
    return module.pages.map((page) => ({
      id: page.id,
      title: buildExplorationPageTaskTitle(page),
      description: page.recent_event || page.structure_summary || page.blocker_reason || "",
      status: resolvePagePlanStatus(page),
      meta: buildExplorationPageTaskMeta(page),
      steps: page.steps,
    }));
  }
  if (!isActiveStatus(detail.run.status) && !module.completion_summary && !detail.run.result_summary) {
    return [];
  }
  const status = resolveModulePlanStatus(detail.run.status, module.completion_status);
  const detailText = module.completion_summary || detail.run.result_summary || "等待探索执行。";
  return [
    {
      id: `${module.id}-progress`,
      title: buildModuleProgressSubtaskTitle(detail.run.status),
      description: detailText,
      status,
      meta: [module.entry_path || detail.run.environment_name].filter((item): item is string => Boolean(item)),
      steps: [
        {
          id: `${module.id}-progress-step`,
          title: buildModuleProgressStepTitle(detail.run.status),
          detail: detailText,
          status,
        },
      ],
    },
  ];
}

function buildModuleProgressSubtaskTitle(runStatus: string): string {
  if (isActiveStatus(runStatus)) {
    return "当前运行阶段";
  }
  return "探索阶段记录";
}

function buildModuleProgressStepTitle(runStatus: string): string {
  if (isActiveStatus(runStatus)) {
    return "等待页面事实";
  }
  return "暂无页面事实";
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

function normalizeExplorationRunDetail(data: ExplorationRunDetail): ExplorationRunDetail {
  return data;
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
  return ["completed", "partial", "blocked", "cancelled", "interrupted", "failed"].includes(status);
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
  const [error, setError] = useState("");
  const [failureVisible, setFailureVisible] = useState(true);
  const [activeTab, setActiveTab] = useState("探索概览");
  const [report, setReport] = useState<ExplorationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [streamDetail, setStreamDetail] = useState<ExplorationRunDetail | null>(null);
  const [monitor, setMonitor] = useState<ExplorationMonitorState>(emptyMonitorState);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [environments, setEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [requirements, setRequirements] = useState<RequirementDocument[]>([]);
  const [requirementLoading, setRequirementLoading] = useState(false);
  const [explorationForm, setExplorationForm] = useState<ExplorationForm>(emptyExplorationForm);
  const [durationNow, setDurationNow] = useState(() => Date.now());

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
        setMonitor(emptyMonitorState);
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

    if (!shouldTickRunDuration) {
      return undefined;
    }

    setDurationNow(Date.now());
    const timer = window.setInterval(() => {
      setDurationNow(Date.now());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [run]);

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
            applyStreamEvent(event, { setMonitor, setStreamDetail, setRun });
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

  function clearExplorationOutputs() {
    setDetail(null);
    setStreamDetail(null);
    setReport(null);
    setReportError("");
    setReportLoading(false);
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
      const data = await apiRequest<ExplorationEnvironment[]>("/environments");
      setEnvironments(data);
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "环境列表加载失败",
        actionLabel: "加载环境列表",
        method: "GET",
        path: "/environments",
      });
    } finally {
      setEnvironmentLoading(false);
    }
  }

  async function loadRequirements() {
    setRequirementLoading(true);
    try {
      const data = await apiRequest<RequirementDocument[]>(`/projects/${params.projectId}/requirements`);
      setRequirements(data);
      setExplorationForm((current) => ({
        ...current,
        requirementDocId: data.some(
          (item) => item.id === current.requirementDocId && isExplorationLinkableRequirement(item),
        )
          ? current.requirementDocId
          : "",
      }));
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "需求列表加载失败",
        actionLabel: "加载需求",
        method: "GET",
        path: `/projects/${params.projectId}/requirements`,
      });
    } finally {
      setRequirementLoading(false);
    }
  }

  function openEditDialog() {
    if (!run) {
      return;
    }
    setExplorationForm({
      title: run.title,
      environmentId: run.environment_id,
      requirementDocId: run.requirement_doc_id,
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
    if (requirements.length === 0) {
      void loadRequirements();
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
          requirement_doc_id: explorationForm.requirementDocId,
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

  const canStart = run
    ? ["pending", "partial", "completed", "blocked", "cancelled", "interrupted", "failed"].includes(run.status)
    : false;
  const canStop = run ? stoppableStatuses.has(run.status) : false;
  const canEdit = run ? !["queued", "running", "stopping"].includes(run.status) : false;
  const saveDisabled = !explorationForm.title.trim() || !explorationForm.environmentId || saving;
  const availableRequirements = useMemo(() => {
    const linkable = requirements.filter(
      (requirement) => requirement.status !== "archived" && isExplorationLinkableRequirement(requirement),
    );
    const linkedRequirementId = explorationForm.requirementDocId;
    if (!linkedRequirementId) {
      return linkable;
    }
    const linkedRequirement = requirements.find((requirement) => requirement.id === linkedRequirementId);
    if (!linkedRequirement || linkable.some((requirement) => requirement.id === linkedRequirementId)) {
      return linkable;
    }
    return [linkedRequirement, ...linkable];
  }, [explorationForm.requirementDocId, requirements]);
  const activeDetail = streamDetail ?? detail;
  const isUnsupportedArtifact = Boolean(activeDetail?.unsupported_artifact);
  const unsupportedArtifactReason = activeDetail?.unsupported_reason || "历史产物格式不支持新版详情，请重新探索。";
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
            {activeTab === "探索计划" ? (
              <Button disabled={!canEdit} onClick={openEditDialog} size="sm" variant="outline">
                <Pencil className="size-4" />
                编辑
              </Button>
            ) : null}
            {canStart ? (
              <Button disabled={starting} onClick={() => void startExploration()} size="sm">
                <Play className="size-4" />
                {run && hasExplorationStarted(run) ? "重新探索" : "开始探索"}
              </Button>
            ) : null}
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
      tabs={["探索计划", "探索概览", "探索报告"]}
      title={run?.title ?? "探索任务"}
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}

      {activeTab === "探索计划" ? <ExplorationTaskInfoPanel monitor={monitor} run={run} /> : null}

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
              <div className="rounded-lg border bg-muted/20 p-8 text-center text-muted-foreground text-sm">
                暂无探索模块进度信息
              </div>
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
        </>
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
                id="exploration-environment"
                placeholder={environmentLoading ? "环境加载中" : "选择环境"}
                setValue={(value) => setExplorationForm((current) => ({ ...current, environmentId: value }))}
                value={explorationForm.environmentId}
              >
                {environments.map((environment) => (
                  <SelectOption key={environment.id} value={environment.id}>
                    {environment.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="exploration-requirement">需求</FieldLabel>
              <Select
                disabled={requirementLoading}
                id="exploration-requirement"
                placeholder={requirementLoading ? "需求加载中" : "选择需求或留空"}
                setValue={(value) =>
                  setExplorationForm((current) => ({
                    ...current,
                    requirementDocId: value === NO_REQUIREMENT_VALUE ? "" : value,
                  }))
                }
                value={explorationForm.requirementDocId || NO_REQUIREMENT_VALUE}
              >
                <SelectOption value={NO_REQUIREMENT_VALUE}>不关联需求</SelectOption>
                {availableRequirements.map((requirement) => (
                  <SelectOption key={requirement.id} value={requirement.id}>
                    {requirement.name}
                  </SelectOption>
                ))}
              </Select>
              {!requirementLoading && availableRequirements.length === 0 ? (
                <p className="text-muted-foreground text-xs">当前项目没有可关联的需求，请先完成需求分析。</p>
              ) : null}
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
    </PageShell>
  );
}

function ExplorationFailureNotice({ error, onClose }: { error: string; onClose: () => void }) {
  return (
    <div className="flex min-h-10 items-center gap-2 rounded-lg border border-destructive/35 bg-destructive/8 px-3 text-sm shadow-sm">
      <AlertTriangle className="size-4 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1 truncate text-destructive">
        探索任务加载失败：{error}。
      </div>
      <Button aria-label="关闭探索失败信息" onClick={onClose} size="icon-xs" type="button" variant="ghost">
        <X className="size-4" />
      </Button>
    </div>
  );
}

function ExplorationTaskInfoPanel({ monitor, run }: { monitor: ExplorationMonitorState; run: ExplorationRun | null }) {
  const loginStrategy = run ? (loginStrategyLabels[run.login_strategy] ?? run.login_strategy) : "-";
  const scopeParagraphs = formatTaskText(run?.scope);
  const forbiddenPathParagraphs = formatTaskText(run?.forbidden_paths);
  const goalParagraphs = formatTaskText(run?.goal);

  return (
    <div className="space-y-4">
      <ExplorationRealtimeMonitor monitor={monitor} run={run} />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <TaskTextSection paragraphs={scopeParagraphs} title="探索范围" />
          <TaskTextSection paragraphs={forbiddenPathParagraphs} title="禁止路径" />
          <TaskTextSection paragraphs={goalParagraphs} title="探索目标" />
        </div>

        <div className="space-y-4">
          <TaskSection title="环境">
            <InfoRow label="所属项目" value={displayValue(run?.project_name)} compact />
            <InfoRow label="关联需求" value={displayValue(run?.requirement_doc_title)} compact />
            <InfoRow label="探索环境" value={displayValue(run?.environment_name)} compact />
            <InfoRow label="登录策略" value={loginStrategy} compact />
            <InfoRow label="站点地址" value={displayValue(run?.environment_site_url)} compact />
          </TaskSection>

          <TaskSection title="执行边界">
            <div className="grid grid-cols-3 gap-2">
              <LimitTile label="页面" value={run ? `${run.max_pages ?? 50}` : "-"} unit="页" />
              <LimitTile label="操作" value={run ? `${run.max_actions ?? 1000}` : "-"} unit="次" />
              <LimitTile label="超时" value={run ? `${run.timeout_minutes ?? 120}` : "-"} unit="分钟" />
            </div>
          </TaskSection>

          <TaskSection title="补充信息">
            <InfoRow label="备注" value={displayValue(run?.notes)} compact />
          </TaskSection>
        </div>
      </div>
    </div>
  );
}

function ExplorationRealtimeMonitor({
  monitor,
  run,
}: {
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
}) {
  const runningStep = monitor.steps.find((step) => step.status === "running");
  const completedCount = monitor.steps.filter((step) => step.status === "completed").length;
  const failedCount = monitor.steps.filter((step) => step.status === "failed").length;
  const totalSteps = monitor.plan?.total_steps || monitor.steps.length;
  const phaseLabel = monitorPhaseLabel(monitor.phase, run?.status);

  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-sm">
              <ListChecks className="size-4" />
              实时执行监控
            </CardTitle>
            <CardDescription>展示规划结果、当前步骤和后台事件流水</CardDescription>
          </div>
          <StatusBadge tone={monitorPhaseTone(monitor.phase, run?.status)}>{phaseLabel}</StatusBadge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <MonitorStat label="规划步骤" value={totalSteps ? `${totalSteps}` : "-"} />
          <MonitorStat label="已完成" value={`${completedCount}`} />
          <MonitorStat label="失败" value={`${failedCount}`} />
          <MonitorStat label="当前步骤" value={runningStep ? `#${runningStep.step_number}` : "-"} />
        </div>

        {monitor.plan ? (
          <div className="grid gap-3 rounded-lg border bg-muted/15 p-3 text-sm lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="min-w-0 space-y-2">
              <InfoRow label="目标摘要" value={displayValue(monitor.plan.goal_summary)} compact />
              <InfoRow label="探索策略" value={displayValue(monitor.plan.strategy)} compact />
              <InfoRow label="范围摘要" value={displayValue(monitor.plan.scope_summary)} compact />
              {monitor.plan.risk_assessment ? (
                <InfoRow label="风险提示" value={monitor.plan.risk_assessment} compact />
              ) : null}
            </div>
            <div className="min-w-0 space-y-2">
              <InfoRow label="计划 ID" value={displayValue(monitor.plan.plan_id)} compact />
              <InfoRow
                label="模块"
                value={monitor.plan.modules.length ? monitor.plan.modules.join("、") : "-"}
                compact
              />
              <InfoRow
                label="成功标准"
                value={monitor.plan.success_criteria.length ? monitor.plan.success_criteria.join("；") : "-"}
                compact
              />
            </div>
          </div>
        ) : (
          <div className="rounded-lg border bg-muted/15 p-3 text-muted-foreground text-sm">
            {isActiveStatus(run?.status ?? "") ? "等待后端推送探索规划。" : "开始探索后会在这里展示实时规划和步骤。"}
          </div>
        )}

        {runningStep ? <MonitorCurrentStep step={runningStep} /> : null}

        {monitor.steps.length ? (
          <div className="overflow-hidden rounded-lg border">
            <Table className="table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[8%]">序号</TableHead>
                  <TableHead className="w-[14%]">状态</TableHead>
                  <TableHead className="w-[18%]">动作</TableHead>
                  <TableHead className="w-[30%]">目标</TableHead>
                  <TableHead className="w-[18%]">结果</TableHead>
                  <TableHead className="w-[12%]">耗时</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {monitor.steps.map((step) => (
                  <TableRow key={step.step_id}>
                    <TableCell className="font-mono text-xs">#{step.step_number}</TableCell>
                    <TableCell>
                      <StatusBadge tone={monitorStepTone(step.status)}>{monitorStepLabel(step.status)}</StatusBadge>
                    </TableCell>
                    <TableCell className="truncate" title={step.description}>
                      {step.action_type}
                    </TableCell>
                    <TableCell className="truncate" title={step.target_description || step.description}>
                      {step.target_description || step.description}
                    </TableCell>
                    <TableCell className="truncate" title={step.message || step.error || step.expected_result}>
                      {step.message || step.error || step.expected_result || "-"}
                    </TableCell>
                    <TableCell>{step.duration_ms === null ? "-" : `${step.duration_ms}ms`}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}

        {monitor.events.length ? (
          <div className="space-y-2">
            <div className="font-medium text-muted-foreground text-xs">实时事件</div>
            <div className="max-h-56 space-y-2 overflow-auto rounded-lg border bg-background p-2">
              {monitor.events.slice(0, 12).map((event) => (
                <div className="grid gap-1 rounded-md px-2 py-1.5 text-sm" key={event.id}>
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <span className="font-medium">{event.label}</span>
                    <span className="shrink-0 text-muted-foreground text-xs">{formatDateTime(event.occurred_at)}</span>
                  </div>
                  <div className="truncate text-muted-foreground text-xs" title={event.summary}>
                    {event.summary}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MonitorStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 font-semibold text-lg">{value}</div>
    </div>
  );
}

function MonitorCurrentStep({ step }: { step: ExplorationMonitorStep }) {
  const matchedLabel = step.matched_element.name || step.matched_element.id || "-";
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/70 p-3 text-sm dark:border-blue-500/30 dark:bg-blue-500/10">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="font-medium">正在执行 #{step.step_number}：{step.description}</div>
        <span className="text-muted-foreground text-xs">第 {step.attempt || 1} 次</span>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <InfoRow label="目标" value={displayValue(step.target_description)} compact />
        <InfoRow label="预期" value={displayValue(step.expected_result)} compact />
        <InfoRow label="匹配元素" value={matchedLabel} compact />
        <InfoRow label="当前页面" value={step.page_state.url || step.page_state.title || "-"} compact />
      </div>
    </div>
  );
}

function monitorPhaseLabel(phase: string, runStatus?: string): string {
  if (phase === "planning") return "规划中";
  if (phase === "planned") return "已生成计划";
  if (phase === "executing") return "执行中";
  if (phase === "replanning") return "重新规划";
  if (phase === "completed") return "已完成";
  if (phase === "failed") return "失败";
  if (phase === "cancelled") return "已中止";
  return runStatus ? (statusLabels[runStatus] ?? runStatus) : "待开始";
}

function monitorPhaseTone(phase: string, runStatus?: string): StatusBadgeTone {
  if (phase === "completed") return "success";
  if (phase === "failed") return "destructive";
  if (phase === "cancelled" || phase === "replanning") return "warning";
  if (phase === "planning" || phase === "planned" || phase === "executing") return "processing";
  if (runStatus === "completed") return "success";
  if (runStatus === "blocked" || runStatus === "failed") return "destructive";
  if (runStatus === "running" || runStatus === "queued") return "processing";
  return "neutral";
}

function monitorStepLabel(status: AgentPlanStatus): string {
  if (status === "running" || status === "in-progress") return "执行中";
  if (status === "completed") return "完成";
  if (status === "failed") return "失败";
  if (status === "partial") return "跳过";
  return "待执行";
}

function monitorStepTone(status: AgentPlanStatus): StatusBadgeTone {
  if (status === "completed") return "success";
  if (status === "failed" || status === "blocked") return "destructive";
  if (status === "running" || status === "in-progress") return "processing";
  if (status === "partial" || status === "cancelled") return "warning";
  return "neutral";
}

function TaskTextSection({ paragraphs, title }: { paragraphs: string[]; title: string }) {
  return (
    <TaskSection title={title}>
      {paragraphs.length ? (
        <div className="space-y-3 text-foreground text-sm leading-7">
          {paragraphs.map((paragraph) => (
            <p className="max-w-5xl whitespace-pre-wrap break-words" key={paragraph}>
              {paragraph}
            </p>
          ))}
        </div>
      ) : (
        <div className="text-muted-foreground text-sm">未设置</div>
      )}
    </TaskSection>
  );
}

function LimitTile({ label, unit, value }: { label: string; unit: string; value: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="font-semibold text-lg">{value}</span>
        <span className="text-muted-foreground text-xs">{unit}</span>
      </div>
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

function UnsupportedArtifactNotice({
  onRestart,
  reason,
  restarting,
}: {
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
          <Button disabled={restarting} onClick={() => void onRestart()} size="sm" type="button">
            <Play className="size-4" />
            重新探索
          </Button>
        </div>
      </div>
    </div>
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

function InfoRow({ compact = false, label, value }: { compact?: boolean; label: string; value: string }) {
  return (
    <div
      className={
        compact
          ? "grid gap-1 border-b pb-2 last:border-b-0 last:pb-0"
          : "grid gap-1 border-b pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[96px_1fr]"
      }
    >
      <div className="text-muted-foreground">{label}</div>
      <div className="min-w-0 break-words font-medium">{value}</div>
    </div>
  );
}

function displayValue(value: string | null | undefined): string {
  return value?.trim() || "-";
}

function formatTaskText(value: string | null | undefined): string[] {
  const text = value?.trim();
  if (!text || text === "-") {
    return [];
  }
  const normalized = text
    .replace(/\s+(模块[一二三四五六七八九十]+[：:])/g, "\n$1")
    .replace(/\s+(整体目标[：:])/g, "\n$1")
    .replace(/\s+(\d+[.、]\s*)/g, "\n$1");
  return normalized
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);
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
