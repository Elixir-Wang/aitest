"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  Circle,
  CircleAlert,
  CircleDotDashed,
  CircleX,
  ListChecks,
  Loader2,
  Play,
  RefreshCw,
  Square,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import type { AgentPlanStatus, AgentPlanTask } from "@/components/ui/agent-plan";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { API_BASE_URL, apiAuthHeaders, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError as reportApiError } from "@/lib/error-feedback";

type ExplorationMode = "goal" | "autonomous";

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
  exploration_mode: ExplorationMode;
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
  raw_events?: PersistedExplorationEvent[];
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
  display?: ReadableExecutionDisplay;
};

type PersistedExplorationEvent = {
  event_id?: string | number;
  type: string;
  run_id?: string;
  payload?: Record<string, unknown>;
  occurred_at?: string;
  timestamp?: string;
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
  payload?: Record<string, unknown>;
  display?: ReadableExecutionDisplay;
};

type ReadableExecutionDisplayKind =
  | "model_analysis"
  | "navigate"
  | "click"
  | "snapshot"
  | "file_read"
  | "artifact_write"
  | "todo_update"
  | "url_record"
  | "error"
  | "debug";

type ReadableExecutionField = {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "default" | "success" | "warning" | "danger";
};

type ReadableExecutionDisplay = {
  kind: ReadableExecutionDisplayKind;
  title: string;
  summary: string;
  fields?: ReadableExecutionField[];
  chips?: string[];
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
    setters.setStreamDetail((current) => mergeDetailSnapshot(current, snapshot));
    setters.setMonitor(finalizeRunningMonitorSteps(monitorFromRunDetail(snapshot), snapshot.run.status));
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
    const status = stringValue((event.payload as Partial<ExplorationRun>).status);
    if (isTerminalStatus(status)) {
      setters.setMonitor((current) => finalizeRunningMonitorSteps(current, status));
    }
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
    events: [monitorTimelineEvent(event), ...next.events],
  };
}

function finalizeRunningMonitorSteps(monitor: ExplorationMonitorState, runStatus: string): ExplorationMonitorState {
  if (!isTerminalStatus(runStatus)) {
    return monitor;
  }
  const finalStatus = finalMonitorStepStatusFromRunStatus(runStatus);
  if (!finalStatus) {
    return monitor;
  }
  const hasRunningSteps = monitor.steps.some((step) => step.status === "running" || step.status === "in-progress");
  if (!hasRunningSteps) {
    return monitor;
  }
  return {
    ...monitor,
    steps: monitor.steps.map((step) =>
      step.status === "running" || step.status === "in-progress"
        ? {
            ...step,
            status: finalStatus,
            completed_at: step.completed_at || new Date().toISOString(),
            message: step.message || finalMonitorStepMessage(runStatus),
          }
        : step,
    ),
  };
}

function finalMonitorStepStatusFromRunStatus(runStatus: string): AgentPlanStatus | null {
  if (runStatus === "completed" || runStatus === "partial") {
    return "completed";
  }
  if (runStatus === "failed" || runStatus === "blocked" || runStatus === "interrupted") {
    return "failed";
  }
  if (runStatus === "cancelled") {
    return "cancelled";
  }
  return null;
}

function finalMonitorStepMessage(runStatus: string): string {
  if (runStatus === "completed" || runStatus === "partial") {
    return "探索任务已结束。";
  }
  if (runStatus === "cancelled") {
    return "探索任务已中止。";
  }
  return "探索任务失败，执行流已终止。";
}

function mergeDetailSnapshot(
  current: ExplorationRunDetail | null,
  incoming: ExplorationRunDetail,
): ExplorationRunDetail {
  if (!current || incoming.modules.length > 0) {
    return incoming;
  }
  if (current.run.id !== incoming.run.id || current.modules.length === 0) {
    return incoming;
  }
  return {
    ...incoming,
    modules: current.modules,
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
  const rawEvents = persistedMonitorEventsFromDetail(detail).reverse();
  const events = steps
    .filter((step) => step.message || step.status !== "pending")
    .reverse()
    .map((step) => ({
      id: `snapshot-${step.step_id}`,
      type: "run_snapshot",
      label: "当前步骤",
      summary: step.message || step.description,
      occurred_at: step.completed_at || detail.run.updated_at,
      status: step.status,
    }));
  events.unshift(...rawEvents);
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

function persistedMonitorEventsFromDetail(detail: ExplorationRunDetail): ExplorationMonitorEvent[] {
  const rawEvents = Array.isArray(detail.raw_events) ? detail.raw_events : [];
  return rawEvents
    .filter((event) => event && typeof event.type === "string")
    .map((event, index) => {
      const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
      const streamEvent = stringValue(payload.event);
      const streamName = stringValue(payload.name);
      const summary =
        stringValue(payload.message) ||
        stringValue(payload.error) ||
        stringValue(payload.output) ||
        stringValue(payload.input) ||
        streamName ||
        streamEvent ||
        event.type;
      return {
        id: `persisted-${event.event_id || index}`,
        type: event.type,
        label: logTypeLabels[event.type] ?? event.type,
        summary,
        occurred_at: stringValue(event.occurred_at || event.timestamp) || detail.run.updated_at,
        status: persistedMonitorEventStatus(event.type, payload),
        payload,
        display: readableDisplayFromPayload(event as unknown as Record<string, unknown>),
      };
    });
}

function persistedMonitorEventStatus(eventType: string, payload: Record<string, unknown>): AgentPlanStatus {
  const streamEvent = stringValue(payload.event);
  if (streamEvent === "on_tool_error" || streamEvent === "on_chain_error" || payload.error) {
    return "failed";
  }
  if (streamEvent.endsWith("_end") || eventType.endsWith("_completed")) {
    return "completed";
  }
  if (streamEvent.endsWith("_start") || eventType.endsWith("_started")) {
    return "running";
  }
  return monitorTimelineStatus(eventType);
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

function upsertMonitorStep(
  steps: ExplorationMonitorStep[],
  incoming: ExplorationMonitorStep,
): ExplorationMonitorStep[] {
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
    occurred_at:
      stringValue(payload.completed_at || payload.started_at || payload.occurred_at) || new Date().toISOString(),
    status: monitorTimelineStatus(event.type),
    payload,
    display: event.display ?? readableDisplayFromPayload(payload),
  };
}

function monitorTimelineStatus(eventType: string): AgentPlanStatus {
  if (eventType.includes("failed") || eventType === "error") return "failed";
  if (eventType.includes("completed")) return "completed";
  if (eventType.includes("cancelled")) return "cancelled";
  if (eventType.includes("started") || eventType === "step_retrying") return "running";
  return "pending";
}

function readableDisplayFromPayload(payload: Record<string, unknown>): ReadableExecutionDisplay | undefined {
  const display = payload.display;
  if (!display || typeof display !== "object") {
    return undefined;
  }
  const record = display as Record<string, unknown>;
  const kind = stringValue(record.kind) as ReadableExecutionDisplayKind;
  if (!kind || !stringValue(record.title)) {
    return undefined;
  }
  const fieldsValue = record.fields;
  const fields = Array.isArray(fieldsValue)
    ? fieldsValue
        .filter((field): field is Record<string, unknown> => Boolean(field) && typeof field === "object")
        .map((field) => ({
          label: stringValue(field.label),
          value: stringValue(field.value),
          mono: Boolean(field.mono),
          tone: stringValue(field.tone) as ReadableExecutionField["tone"],
        }))
        .filter((field) => field.label && field.value)
    : [];
  return {
    kind,
    title: stringValue(record.title),
    summary: stringValue(record.summary),
    fields,
    chips: arrayOfStrings(record.chips),
  };
}

function stringValue(value: unknown): string {
  return value ? String(value) : "";
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

function buildMonitorModuleTasks(monitor?: ExplorationMonitorState): AgentPlanTask[] {
  if (!monitor) {
    return [];
  }
  const moduleNames = [
    ...(monitor.plan?.modules ?? []),
    ...monitor.steps.map((step) => step.module_name).filter(Boolean),
  ];
  const uniqueModuleNames = Array.from(new Set(moduleNames.map((name) => name.trim()).filter(Boolean)));
  const fallbackModuleNames = uniqueModuleNames.length
    ? uniqueModuleNames
    : monitor.events.length
      ? ["主探索模块"]
      : [];

  return fallbackModuleNames.map((moduleName, index) => {
    const moduleSteps = monitor.steps.filter(
      (step) => step.module_name === moduleName || uniqueModuleNames.length === 0,
    );
    const completedSteps = moduleSteps.filter((step) => step.status === "completed").length;
    const failedSteps = moduleSteps.filter((step) => step.status === "failed" || step.status === "blocked").length;
    const runningSteps = moduleSteps.filter(
      (step) => step.status === "running" || step.status === "in-progress",
    ).length;
    const status: AgentPlanStatus = failedSteps
      ? "failed"
      : runningSteps
        ? "running"
        : moduleSteps.length > 0 && completedSteps === moduleSteps.length
          ? "completed"
          : "queued";

    return {
      id: `monitor-module-${index}-${moduleName}`,
      title: moduleName,
      description: monitor.plan?.scope_summary || monitor.plan?.goal_summary || "正在根据实时事件建立探索地图。",
      status,
      meta: moduleSteps.length
        ? [`${completedSteps}/${moduleSteps.length} 步骤`, `${failedSteps} 异常`]
        : ["等待页面事实"],
      subtasks: moduleSteps.slice(0, 8).map((step) => ({
        id: step.step_id,
        title: buildMonitorStepTaskTitle(step),
        description: step.message || step.target_description || step.expected_result || "等待工具返回结果。",
        status: step.status,
        meta: [step.action_type, step.page_state.title || step.page_state.url].filter(Boolean),
      })),
    };
  });
}

function buildMonitorStepTaskTitle(step: ExplorationMonitorStep): string {
  if (step.action_type === "write_page_artifact_tool") {
    return "写入页面事实";
  }
  if (step.action_type?.startsWith("playwright_")) {
    return step.description || step.action_type.replace(/^playwright_/, "页面操作：");
  }
  if (step.action_type === "model") {
    return "分析页面与下一步动作";
  }
  if (step.action_type === "tools") {
    return "执行工具调用";
  }
  return step.description || step.action_type || "探索步骤";
}

function _resolvePagePlanStatus(page: ExplorationPage): AgentPlanStatus {
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

function _buildExplorationPageTaskTitle(page: ExplorationPage): string {
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

function _buildExplorationPageTaskMeta(page: ExplorationPage): string[] {
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

function _resolveModulePlanStatus(runStatus: string, moduleStatus: string): AgentPlanStatus {
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
  const router = useRouter();
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
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [reportPrefetchedForRunId, setReportPrefetchedForRunId] = useState("");

  const loadRun = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }
      setError("");
      setFailureVisible(true);
      try {
        const data = await apiRequest<ExplorationRunDetail>(`/page-exploration/runs/${params.runId}`);
        const normalizedData = normalizeExplorationRunDetail(data);
        setDetail(normalizedData);
        setStreamDetail((current) => mergeDetailSnapshot(current, normalizedData));
        setMonitor((current) => {
          const snapshot = finalizeRunningMonitorSteps(monitorFromRunDetail(normalizedData), normalizedData.run.status);
          return current.events.length ? { ...snapshot, events: current.events } : snapshot;
        });
        setRun(normalizedData.run);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "探索任务加载失败");
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [params.runId],
  );

  useEffect(() => {
    void loadRun();
  }, [loadRun]);

  const runStatus = run?.status;

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
        const response = await fetch(`${API_BASE_URL}/page-exploration/runs/${params.runId}/stream`, {
          headers,
          signal: controller.signal,
        });

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
  }, [loadRun, params.runId, runStatus]);

  const loadReport = useCallback(async () => {
    setReportLoading(true);
    setReportError("");
    try {
      const data = await apiRequest<ExplorationReport>(`/page-exploration/runs/${params.runId}/artifacts`);
      setReport(data);
    } catch (requestError) {
      setReportError(requestError instanceof Error ? requestError.message : "探索报告加载失败");
    } finally {
      setReportLoading(false);
    }
  }, [params.runId]);

  useEffect(() => {
    if (activeTab === "探索报告") {
      void loadReport();
    }
  }, [activeTab, loadReport]);

  useEffect(() => {
    if (run?.status !== "completed" || reportPrefetchedForRunId === run.id) {
      return;
    }
    setReportPrefetchedForRunId(run.id);
    void loadReport();
  }, [loadReport, reportPrefetchedForRunId, run?.id, run?.status]);

  async function refreshCurrentTab() {
    await loadRun();
    if (activeTab === "探索报告") {
      await loadReport();
    }
  }

  async function startExploration() {
    if (!run) {
      return;
    }
    const restarting = hasExplorationStarted(run);
    setStarting(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${run.id}/start`, {
        method: "POST",
      });
      setRun(updated);
      notifyAiTaskStarted();
      toast.success(restarting ? "重新探索已开始" : "探索任务已开始");
      window.setTimeout(() => void loadRun({ silent: true }), 800);
    } catch (requestError) {
      reportApiError(requestError, {
        fallbackMessage: "探索任务启动失败",
        actionLabel: restarting ? "重新探索" : "启动探索任务",
        method: "POST",
        path: `/page-exploration/runs/${run.id}/start`,
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
      const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${run.id}/stop`, {
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
        path: `/page-exploration/runs/${run.id}/stop`,
      });
    } finally {
      setStopping(false);
    }
  }

  const canStart = run
    ? ["pending", "partial", "completed", "blocked", "cancelled", "interrupted", "failed"].includes(run.status)
    : false;
  const canStop = run ? stoppableStatuses.has(run.status) : false;
  const activeDetail = streamDetail ?? detail;
  const isUnsupportedArtifact = Boolean(activeDetail?.unsupported_artifact);
  const unsupportedArtifactReason = activeDetail?.unsupported_reason || "历史产物格式不支持新版详情，请重新探索。";
  const templateLabel = run?.exploration_mode === "goal" ? "目标探索模板" : "自主探索";
  return (
    <PageShell
      breadcrumbs={["项目", projectName, "探索", run?.title ?? "探索任务"]}
      tabActions={
        <>
          <Button onClick={() => router.push("/exploration")} size="sm" variant="outline">
            <ArrowLeft className="size-4" />
            返回列表
          </Button>
          {activeTab === "探索概览" ? (
            <Button disabled={loading} onClick={() => void refreshCurrentTab()} size="sm" variant="outline">
              <RefreshCw className="size-4" />
              刷新
            </Button>
          ) : null}
          {activeTab === "探索概览" ? (
            <>
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
          ) : null}
        </>
      }
      projectScope="project"
      activeTab={activeTab}
      fillViewport
      onTabChange={setActiveTab}
      tabs={["探索概览", "探索报告"]}
      title={run?.title ?? "探索任务"}
      description={`查看${templateLabel}、执行结果和探索报告。`}
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}
      {activeTab === "探索概览" ? (
        <ExplorationModuleProgressPanel
          isUnsupportedArtifact={isUnsupportedArtifact}
          loading={loading}
          monitor={monitor}
          onRestart={startExploration}
          restarting={starting}
          run={run}
          unsupportedArtifactReason={unsupportedArtifactReason}
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
      <div className="min-w-0 flex-1 truncate text-destructive">探索任务加载失败：{error}。</div>
      <Button aria-label="关闭探索失败信息" onClick={onClose} size="icon-xs" type="button" variant="ghost">
        <X className="size-4" />
      </Button>
    </div>
  );
}

function ExplorationModuleProgressPanel({
  isUnsupportedArtifact,
  loading,
  monitor,
  onRestart,
  restarting,
  run,
  unsupportedArtifactReason,
}: {
  isUnsupportedArtifact: boolean;
  loading: boolean;
  monitor: ExplorationMonitorState;
  onRestart: () => Promise<void> | void;
  restarting: boolean;
  run: ExplorationRun | null;
  unsupportedArtifactReason: string;
}) {
  return (
    <div className="grid min-h-[480px] min-w-0 flex-1 gap-4 lg:min-h-0 lg:grid-cols-[360px_minmax(0,1fr)]">
      <ExplorationStageSidebar
        isUnsupportedArtifact={isUnsupportedArtifact}
        loading={loading}
        monitor={monitor}
        onRestart={onRestart}
        restarting={restarting}
        run={run}
        unsupportedArtifactReason={unsupportedArtifactReason}
      />
      <ExplorationConversationPanel loading={loading} monitor={monitor} run={run} />
    </div>
  );
}

function buildExplorationStageRows(monitor: ExplorationMonitorState): AgentPlanTask[] {
  return buildTemplatePlanTasks(monitor);
}

type ExplorationConversationEntry = {
  id: string;
  kind: "message" | "tool";
  role: "user" | "assistant" | "system";
  title: string;
  content: string;
  status: AgentPlanStatus;
  occurredAt: string;
  completedAt?: string;
  fields: ReadableExecutionField[];
  chips?: string[];
};

function buildExplorationConversationEntries(monitor: ExplorationMonitorState): ExplorationConversationEntry[] {
  return [...monitor.events].reverse().flatMap((event) => {
    if (event.type === "agent_plan_updated" || event.display?.kind === "todo_update") {
      return [];
    }

    const display = event.display;
    if (display?.kind === "model_analysis") {
      return [
        {
          id: event.id,
          kind: "message",
          role: "assistant",
          title: display.title,
          content: display.summary || event.summary,
          status: event.status,
          occurredAt: event.occurred_at,
          fields: display.fields ?? [],
          chips: display.chips,
        },
      ];
    }

    if (display) {
      return [
        {
          id: event.id,
          kind: "tool",
          role: "system",
          title: display.title,
          content: display.summary || event.summary,
          status: event.status,
          occurredAt: event.occurred_at,
          completedAt: event.occurred_at,
          fields: display.fields ?? [],
          chips: display.chips,
        },
      ];
    }

    if (!isConversationEvent(event.type)) {
      return [];
    }

    return [
      {
        id: event.id,
        kind: "message",
        role: conversationRoleFromEvent(event.type),
        title: event.label,
        content: event.summary,
        status: event.status,
        occurredAt: event.occurred_at,
        fields: [],
      },
    ];
  });
}

function isConversationEvent(eventType: string): boolean {
  return [
    "run_started",
    "planning_started",
    "planning_completed",
    "run_completed",
    "run_failed",
    "run_cancelled",
    "error",
  ].includes(eventType);
}

function conversationRoleFromEvent(eventType: string): "user" | "assistant" | "system" {
  if (eventType === "run_started" || eventType === "planning_started") {
    return "system";
  }
  if (eventType === "run_failed" || eventType === "error") {
    return "assistant";
  }
  return "assistant";
}

function ExplorationStageSidebar({
  isUnsupportedArtifact,
  loading,
  monitor,
  onRestart,
  restarting,
  run,
  unsupportedArtifactReason,
}: {
  isUnsupportedArtifact: boolean;
  loading: boolean;
  monitor: ExplorationMonitorState;
  onRestart: () => Promise<void> | void;
  restarting: boolean;
  run: ExplorationRun | null;
  unsupportedArtifactReason: string;
}) {
  const stageRows = useMemo(() => buildExplorationStageRows(monitor), [monitor]);
  const phaseLabel = monitorPhaseLabel(monitor.phase, run?.status);
  const currentStageId =
    stageRows.find((stage) => stage.status === "running" || stage.status === "in-progress")?.id || "";

  return (
    <section className="min-h-0 min-w-0 overflow-y-auto border-r pr-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-medium text-sm">探索阶段</h2>
          <p className="text-muted-foreground text-xs">显示当前完成到哪一步。</p>
        </div>
        <StatusBadge tone={monitorPhaseTone(monitor.phase, run?.status)}>{phaseLabel}</StatusBadge>
      </div>

      {loading ? (
        <div className="grid min-h-[280px] place-items-center rounded-md border bg-background/70 p-6 text-center text-muted-foreground text-sm">
          阶段清单加载中...
        </div>
      ) : isUnsupportedArtifact ? (
        <UnsupportedArtifactNotice onRestart={onRestart} reason={unsupportedArtifactReason} restarting={restarting} />
      ) : stageRows.length > 0 ? (
        <ol className="space-y-2">
          {stageRows.map((stage) => (
            <li
              className={`rounded-md border px-3 py-2 ${stage.id === currentStageId ? "border-blue-200 bg-blue-50/40 dark:border-blue-500/20 dark:bg-blue-500/8" : "bg-background"}`}
              key={stage.id}
            >
              <div className="flex items-start gap-2">
                <MonitorStatusIcon status={stage.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 truncate text-sm">{stage.title}</div>
                    <StatusBadge tone={monitorStepTone(stage.status)}>{monitorStepLabel(stage.status)}</StatusBadge>
                  </div>
                  {stage.meta?.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {stage.meta.map((meta) => (
                        <span className="max-w-40 truncate text-[11px] text-muted-foreground" key={meta} title={meta}>
                          {meta}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
              {stage.subtasks?.length ? (
                <div className="mt-2 space-y-1.5 border-l pl-3">
                  {stage.subtasks.map((subtask) => (
                    <div className="flex items-start gap-2" key={subtask.id}>
                      <MonitorStatusIcon status={subtask.status} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{subtask.title}</div>
                        {subtask.description ? (
                          <div className="mt-0.5 break-words text-muted-foreground text-xs">{subtask.description}</div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <ExplorationStageEmptyState run={run} />
      )}
    </section>
  );
}

function ExplorationStageEmptyState({ run }: { run: ExplorationRun | null }) {
  const pending = run?.status === "pending";
  const title = pending ? "等待开始探索" : "暂无阶段信息";
  const description = pending ? "点击开始探索后，这里会显示阶段清单。" : "当前还没有可展示的阶段进度。";
  return (
    <div className="grid min-h-[280px] place-items-center rounded-md border bg-background/70 p-6 text-center">
      <div className="max-w-sm space-y-2">
        <div className="mx-auto flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <ListChecks className="size-4" />
        </div>
        <div className="font-medium text-sm">{title}</div>
        <p className="text-muted-foreground text-xs">{description}</p>
      </div>
    </div>
  );
}

function ExplorationConversationPanel({
  loading,
  monitor,
  run,
}: {
  loading: boolean;
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
}) {
  const timeline = useMemo(() => buildExplorationConversationEntries(monitor), [monitor]);
  const phaseLabel = monitorPhaseLabel(monitor.phase, run?.status);
  const eventListRef = useRef<HTMLDivElement | null>(null);
  const shouldFollowBottomRef = useRef(true);
  const previousLatestEventKeyRef = useRef("");
  const [unreadEventCount, setUnreadEventCount] = useState(0);

  const latestEventKey = useMemo(() => {
    const latestItem = timeline.at(-1);
    if (!latestItem) {
      return "";
    }
    return JSON.stringify([
      timeline.length,
      latestItem.id,
      latestItem.status,
      latestItem.content,
      latestItem.occurredAt,
    ]);
  }, [timeline]);

  const isEventListAtBottom = useCallback((list: HTMLDivElement) => {
    const distanceToBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
    return distanceToBottom < 96;
  }, []);

  const scrollToLatestEvent = useCallback(() => {
    const list = eventListRef.current;
    if (!list) {
      return;
    }
    list.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
    shouldFollowBottomRef.current = true;
    setUnreadEventCount(0);
  }, []);

  useLayoutEffect(() => {
    if (!latestEventKey) {
      return;
    }
    if (previousLatestEventKeyRef.current === latestEventKey) {
      return;
    }
    previousLatestEventKeyRef.current = latestEventKey;
    const list = eventListRef.current;
    if (!list) {
      return;
    }
    const shouldFollowLatest = shouldFollowBottomRef.current || isEventListAtBottom(list);
    if (!shouldFollowLatest) {
      setUnreadEventCount((current) => current + 1);
      return;
    }
    window.requestAnimationFrame(() => {
      list.scrollTo({ top: list.scrollHeight });
      shouldFollowBottomRef.current = true;
      setUnreadEventCount(0);
    });
  }, [isEventListAtBottom, latestEventKey]);

  const handleEventListScroll = useCallback(() => {
    const list = eventListRef.current;
    if (!list) {
      return;
    }
    const isAtBottom = isEventListAtBottom(list);
    shouldFollowBottomRef.current = isAtBottom;
    if (isAtBottom) {
      setUnreadEventCount(0);
    }
  }, [isEventListAtBottom]);

  return (
    <section className="min-h-0 min-w-0 overflow-hidden">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-medium text-sm">对话与执行</h2>
          <p className="text-muted-foreground text-xs">展示 Agent 分析、工具调用和关键执行结果。</p>
        </div>
        <StatusBadge tone={monitorPhaseTone(monitor.phase, run?.status)}>{phaseLabel}</StatusBadge>
      </div>

      {loading ? (
        <div className="grid min-h-[280px] place-items-center rounded-md border bg-background/70 p-6 text-center text-muted-foreground text-sm">
          对话流加载中...
        </div>
      ) : timeline.length ? (
        <div className="min-h-0 flex-1 space-y-0 overflow-y-auto" onScroll={handleEventListScroll} ref={eventListRef}>
          {timeline.map((item) =>
            item.kind === "message" ? (
              <ConversationMessageBubble item={item} key={item.id} />
            ) : (
              <ToolCallInlineBlock item={item} key={item.id} />
            ),
          )}
          {unreadEventCount > 0 ? (
            <div className="sticky bottom-2 z-10 flex justify-center">
              <Button className="h-8 rounded-md shadow-md" onClick={scrollToLatestEvent} size="sm" type="button">
                <ArrowDown className="size-3.5" />
                {unreadEventCount} 条新内容
              </Button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="grid min-h-[280px] place-items-center rounded-md border bg-background/70 p-6 text-center text-muted-foreground text-sm">
          等待探索开始后显示对话与执行过程。
        </div>
      )}
    </section>
  );
}

function ConversationMessageBubble({ item }: { item: ExplorationConversationEntry }) {
  return (
    <div className="border-b py-3 text-sm last:border-b-0">
      <div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
        <span className="truncate">{item.title}</span>
        <span className="shrink-0">{formatDateTime(item.occurredAt)}</span>
      </div>
      <div className="mt-2 whitespace-pre-wrap break-words text-sm leading-6">{item.content}</div>
      {item.fields.length ? <ToolCallInlineDetails fields={item.fields} chips={item.chips} /> : null}
    </div>
  );
}

function ToolCallInlineBlock({ item }: { item: ExplorationConversationEntry }) {
  const [expanded, setExpanded] = useState(item.status === "running" || item.status === "failed");
  return (
    <div className="border-b py-3 text-sm last:border-b-0">
      <button
        className="flex w-full items-start gap-2 text-left transition-colors hover:bg-muted/20"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <span className="shrink-0 pt-0.5 text-muted-foreground">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </span>
        <MonitorStatusIcon status={item.status} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate font-medium">{item.title}</div>
              <div className="mt-0.5 line-clamp-2 whitespace-pre-wrap break-words text-muted-foreground text-xs">
                {item.content}
              </div>
            </div>
            <span className="shrink-0 text-[11px] text-muted-foreground">{formatDateTime(item.occurredAt)}</span>
          </div>
          {item.chips?.length ? (
            <div className="mt-1 flex flex-wrap gap-1">
              {item.chips.map((chip) => (
                <span className="max-w-28 truncate text-[11px] text-muted-foreground" key={chip} title={chip}>
                  {chip}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </button>
      {expanded ? (
        <div className="space-y-3 pt-2 pl-6">
          <ToolCallInlineDetails fields={item.fields} />
          <div className="flex items-center gap-2 text-muted-foreground text-xs">
            {item.status === "running" ? <Loader2 className="size-3 animate-spin" /> : null}
            <span>{monitorStepLabel(item.status)}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ToolCallInlineDetails({ chips = [], fields }: { chips?: string[]; fields: ReadableExecutionField[] }) {
  return (
    <div className="space-y-2">
      {fields.length ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {fields.map((field) => (
            <ReadableExecutionFieldRow field={field} key={`${field.label}-${field.value}`} />
          ))}
        </div>
      ) : null}
      {chips.length ? (
        <div className="flex flex-wrap gap-1">
          {chips.map((chip) => (
            <span className="text-[11px] text-muted-foreground" key={chip}>
              {chip}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function buildTemplatePlanTasks(monitor: ExplorationMonitorState): AgentPlanTask[] {
  const planSteps = monitor.plan?.steps ?? [];
  if (!planSteps.length) {
    return buildMonitorModuleTasks(monitor);
  }

  const statusByStep = new Map(monitor.steps.map((step) => [step.step_id, step.status]));
  const groupedByModule = new Map<string, ExplorationMonitorPlanStep[]>();
  for (const step of planSteps) {
    const key = step.module_name || "模板步骤";
    const group = groupedByModule.get(key) ?? [];
    group.push(step);
    groupedByModule.set(key, group);
  }

  return Array.from(groupedByModule.entries()).map(([moduleName, steps], index) => {
    const subtasks = steps.map((step) => {
      const status = statusByStep.get(step.step_id) ?? "queued";
      return {
        id: step.step_id,
        title: `${step.step_number}. ${step.description || step.action_type || "探索步骤"}`,
        description: [step.target_description, step.expected_result].filter(Boolean).join(" · "),
        status,
        meta: [step.action_type, step.target_selector].filter(Boolean),
      };
    });
    const completedCount = subtasks.filter((item) => item.status === "completed").length;
    const failedCount = subtasks.filter((item) => item.status === "failed" || item.status === "blocked").length;
    const runningCount = subtasks.filter((item) => item.status === "running" || item.status === "in-progress").length;
    const status: AgentPlanStatus = failedCount
      ? "failed"
      : runningCount
        ? "running"
        : completedCount === subtasks.length
          ? "completed"
          : "queued";
    return {
      id: `template-step-group-${index}-${moduleName}`,
      title: moduleName,
      status,
      meta: [`${steps.length} 步骤`],
      subtasks,
    };
  });
}

function MonitorStatusIcon({ status }: { status: AgentPlanStatus }) {
  if (status === "completed") {
    return <Check className="size-3.5 shrink-0 text-green-500" />;
  }
  if (status === "running" || status === "in-progress" || status === "queued" || status === "stopping") {
    return <CircleDotDashed className="size-3.5 shrink-0 text-blue-500" />;
  }
  if (status === "failed" || status === "blocked") {
    return <CircleX className="size-3.5 shrink-0 text-red-500" />;
  }
  if (status === "partial" || status === "cancelled" || status === "waiting_human") {
    return <CircleAlert className="size-3.5 shrink-0 text-amber-500" />;
  }
  return <Circle className="size-3.5 shrink-0 text-muted-foreground" />;
}

function monitorStepTone(status: AgentPlanStatus): StatusBadgeTone {
  if (status === "completed") return "success";
  if (status === "failed" || status === "blocked") return "destructive";
  if (status === "running" || status === "in-progress") return "processing";
  if (status === "partial" || status === "cancelled") return "warning";
  return "neutral";
}

function monitorStepLabel(status: AgentPlanStatus): string {
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "blocked") return "阻塞";
  if (status === "running" || status === "in-progress") return "进行中";
  if (status === "partial") return "部分完成";
  if (status === "cancelled") return "已取消";
  if (status === "waiting_human") return "待确认";
  if (status === "queued" || status === "pending") return "待执行";
  return status;
}

function monitorPhaseLabel(phase: string, runStatus?: string): string {
  if (runStatus === "completed") return "已完成";
  if (runStatus === "failed") return "已失败";
  if (runStatus === "cancelled") return "已取消";
  if (phase === "planning") return "规划中";
  if (phase === "executing") return "执行中";
  return "进行中";
}

function monitorPhaseTone(phase: string, runStatus?: string): StatusBadgeTone {
  if (runStatus === "completed") return "success";
  if (runStatus === "failed") return "destructive";
  if (runStatus === "cancelled") return "warning";
  if (phase === "planning") return "processing";
  return "processing";
}

function ReadableExecutionFieldRow({ field }: { field: ReadableExecutionField }) {
  const toneClass =
    field.tone === "danger"
      ? "text-red-600 dark:text-red-400"
      : field.tone === "warning"
        ? "text-amber-600 dark:text-amber-400"
        : field.tone === "success"
          ? "text-green-600 dark:text-green-400"
          : "";
  return (
    <div className="grid gap-1">
      <div className="text-[11px] text-muted-foreground">{field.label}</div>
      <div
        className={
          field.mono
            ? `whitespace-pre-wrap break-words rounded bg-background p-2 font-mono text-xs ${toneClass}`
            : `whitespace-pre-wrap break-words text-xs ${toneClass}`
        }
      >
        {field.value}
      </div>
    </div>
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
