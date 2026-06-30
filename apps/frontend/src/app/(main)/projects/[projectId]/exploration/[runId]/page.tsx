"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import {
  Activity,
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
  Pencil,
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
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Textarea } from "@/components/ui/textarea";
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
  payload?: Record<string, unknown>;
};

type ReadableExecutionCardKind =
  | "run_start"
  | "model_analysis"
  | "navigate"
  | "click"
  | "snapshot"
  | "artifact_write"
  | "todo_update"
  | "url_record"
  | "error"
  | "run_summary"
  | "debug";

type ReadableExecutionField = {
  label: string;
  value: string;
  mono?: boolean;
  tone?: "default" | "success" | "warning" | "danger";
};

type ReadableExecutionCard = {
  id: string;
  kind: ReadableExecutionCardKind;
  title: string;
  summary: string;
  status: AgentPlanStatus;
  occurred_at: string;
  completed_at?: string;
  duration_ms?: number | null;
  fields: ReadableExecutionField[];
  chips?: string[];
  raw_events: ExplorationMonitorEvent[];
  defaultExpanded?: boolean;
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
  explorationMode: ExplorationMode;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};

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
  goal: "填写本次探索要完成或验证的具体流程，例如新建自主规划 agent，进入草稿页，在调试预览对话框输入 hi。",
  autonomousGoal: "可选补充本次自主盘点的关注点，例如重点覆盖创建、配置、对话、分析相关模块。",
};
const explorationModeLabels: Record<ExplorationMode, string> = {
  goal: "目标探索",
  autonomous: "自主探索",
};
const NO_REQUIREMENT_VALUE = "__none__";
const emptyExplorationForm: ExplorationForm = {
  title: "",
  environmentId: "",
  requirementDocId: "",
  explorationMode: "goal",
  scope: "",
  forbiddenPaths: "",
  goal: "",
  notes: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};

function ExplorationModeSwitch({
  value,
  onChange,
}: {
  value: ExplorationMode;
  onChange: (value: ExplorationMode) => void;
}) {
  return (
    <div className="grid gap-2">
      <FieldLabel>探索方式</FieldLabel>
      <div className="relative grid h-10 w-full max-w-sm grid-cols-2 rounded-full bg-muted p-1">
        <span
          className={`absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-full bg-background shadow-sm transition-transform ${
            value === "autonomous" ? "translate-x-full" : "translate-x-0"
          }`}
        />
        {(["goal", "autonomous"] as const).map((mode) => (
          <button
            className={`relative z-10 rounded-full px-3 font-medium text-sm transition-colors ${
              value === mode ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
            key={mode}
            onClick={() => onChange(mode)}
            type="button"
          >
            {explorationModeLabels[mode]}
          </button>
        ))}
      </div>
      <p className="text-muted-foreground text-xs">
        {value === "goal" ? "围绕明确目标验证页面流程。" : "自动盘点当前页面或范围内的主要功能。"}
      </p>
    </div>
  );
}

function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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
  };
}

function monitorTimelineStatus(eventType: string): AgentPlanStatus {
  if (eventType.includes("failed") || eventType === "error") return "failed";
  if (eventType.includes("completed")) return "completed";
  if (eventType.includes("cancelled")) return "cancelled";
  if (eventType.includes("started") || eventType === "step_retrying") return "running";
  return "pending";
}

function buildReadableExecutionCards(
  events: ExplorationMonitorEvent[],
  detail: ExplorationRunDetail | null,
  run: ExplorationRun | null,
): ReadableExecutionCard[] {
  const chronologicalEvents = [...events].reverse();
  const cards: ReadableExecutionCard[] = [];
  const toolCards = new Map<string, ReadableExecutionCard>();
  let latestTodoCardId = "";
  let lastModelRunId = "";

  for (const event of chronologicalEvents) {
    const payload = event.payload ?? {};
    if (event.type === "agent_stream_event") {
      const streamEvent = stringValue(payload.event);
      const streamName = stringValue(payload.name);
      const streamRunId = stringValue(payload.run_id) || event.id;

      if (isHiddenAgentStreamEvent(streamEvent, streamName)) {
        continue;
      }

      if (streamEvent === "on_tool_start") {
        const card = readableToolCardFromEvent(event, "running");
        toolCards.set(streamRunId, card);
        cards.push(card);
        if (card.kind === "todo_update") {
          latestTodoCardId = card.id;
        }
        continue;
      }

      if (streamEvent === "on_tool_end" || streamEvent === "on_tool_error") {
        const existing = toolCards.get(streamRunId);
        const card = readableToolCardFromEvent(
          event,
          streamEvent === "on_tool_error" ? "failed" : "completed",
          existing,
        );
        toolCards.set(streamRunId, card);
        if (existing) {
          const index = cards.findIndex((item) => item.id === existing.id);
          if (index >= 0) {
            cards[index] = card;
          } else {
            cards.push(card);
          }
        } else {
          cards.push(card);
        }
        if (card.kind === "todo_update") {
          latestTodoCardId = card.id;
        }
        continue;
      }

      if (streamEvent === "on_chat_model_end") {
        if (lastModelRunId === streamRunId) {
          continue;
        }
        const modelCard = readableModelCardFromEvent(event);
        if (modelCard) {
          cards.push(modelCard);
          lastModelRunId = streamRunId;
        }
        continue;
      }

      if (streamEvent === "on_chain_end" && streamName === "model" && !lastModelRunId) {
        const modelCard = readableModelCardFromEvent(event);
        if (modelCard) {
          cards.push(modelCard);
        }
        continue;
      }

      if (payload.error) {
        cards.push(readableErrorCardFromEvent(event));
      }
      continue;
    }

    if (event.type === "agent_step_started" || event.type === "run_started" || event.type === "planning_completed") {
      cards.push(readableRunStartCardFromEvent(event, run));
      continue;
    }

    if (event.type === "agent_step_failed" || event.type === "run_failed" || event.type === "error") {
      cards.push(readableErrorCardFromEvent(event));
      continue;
    }

    if (event.type === "agent_step_completed" || event.type === "run_completed") {
      cards.push(readableSummaryCardFromState(event, detail, run, cards));
      continue;
    }

    if (!isDebugOnlyMonitorEvent(event)) {
      cards.push(readableDebugCardFromEvent(event));
    }
  }

  const visibleCards = latestTodoCardId
    ? cards.filter((card) => card.kind !== "todo_update" || card.id === latestTodoCardId)
    : cards;
  if (run && isTerminalStatus(run.status) && !visibleCards.some((card) => card.kind === "run_summary")) {
    visibleCards.push(readableSummaryCardFromState(null, detail, run, visibleCards));
  }
  return visibleCards;
}

function readableRunStartCardFromEvent(
  event: ExplorationMonitorEvent,
  run: ExplorationRun | null,
): ReadableExecutionCard {
  const payload = event.payload ?? {};
  const fields: ReadableExecutionField[] = [
    { label: "目标", value: run?.goal || event.summary },
    { label: "入口", value: compactUrl(run?.environment_site_url || stringValue(payload.url)), mono: true },
    { label: "范围", value: run?.scope || stringValue(payload.scope_summary) },
    { label: "上限", value: run?.max_pages ? `最多 ${run.max_pages} 个页面` : "" },
    { label: "策略", value: stringValue(payload.strategy) || "使用浏览器工具探索页面并生成页面事实。" },
  ].filter((field) => field.value);
  return {
    id: `readable-${event.id}`,
    kind: "run_start",
    title: "页面探索开始",
    summary: stringValue(payload.message) || event.summary || "页面探索 Agent 已开始执行。",
    status: event.status,
    occurred_at: event.occurred_at,
    fields,
    raw_events: [event],
    defaultExpanded: true,
  };
}

function readableModelCardFromEvent(event: ExplorationMonitorEvent): ReadableExecutionCard | null {
  const payload = event.payload ?? {};
  const output = stringValue(payload.output);
  const error = stringValue(payload.error);
  if (!output && !error) {
    return null;
  }
  const modelName = extractModelName(output) || stringValue(payload.name);
  const intent = extractModelIntent(output);
  const toolNames = extractToolNames(output);
  if (!intent && !toolNames.length && !/finish_reason.*tool_calls|tool_calls/.test(output)) {
    return null;
  }
  return {
    id: `readable-${event.id}`,
    kind: "model_analysis",
    title: "模型分析",
    summary: intent || "模型请求工具调用，准备继续执行页面探索。",
    status: error ? "failed" : "completed",
    occurred_at: event.occurred_at,
    fields: [
      { label: "模型", value: modelName },
      { label: "意图", value: intent },
      { label: "下一步", value: toolNames.slice(0, 4).join(" / ") },
      { label: "结束原因", value: extractFinishReason(output) },
    ].filter((field) => field.value),
    chips: toolNames.slice(0, 3),
    raw_events: [event],
  };
}

function readableToolCardFromEvent(
  event: ExplorationMonitorEvent,
  status: AgentPlanStatus,
  existing?: ReadableExecutionCard,
): ReadableExecutionCard {
  const payload = event.payload ?? {};
  const toolName = stringValue(payload.name);
  const input = parseJsonLikePayload(stringValue(payload.input));
  const output = parseJsonLikePayload(stringValue(payload.output));
  const error = stringValue(payload.error) || extractToolError(output);
  const baseEvents = existing?.raw_events ?? [];
  const rawEvents = [...baseEvents, event];
  const occurredAt = existing?.occurred_at || event.occurred_at;
  const durationMs = status === "running" ? null : durationBetween(occurredAt, event.occurred_at);
  const finalStatus: AgentPlanStatus = error ? "failed" : status;

  if (toolName === "playwright_navigate_tool") {
    const targetUrl = stringFromRecord(input, "url");
    const currentUrl = stringFromRecord(output, "url");
    return createReadableToolCard({
      event,
      existing,
      kind: "navigate",
      title: error ? "打开页面失败" : "打开页面",
      summary: error ? explainError(error).reason : `打开 ${compactUrl(currentUrl || targetUrl) || "目标页面"}`,
      status: finalStatus,
      fields: [
        { label: "目标 URL", value: compactUrl(targetUrl), mono: true },
        { label: "当前页面", value: compactUrl(currentUrl), mono: true },
        {
          label: "结果",
          value: error ? "失败" : status === "running" ? "执行中" : "成功",
          tone: error ? "danger" : "success",
        },
        { label: "原因", value: error ? explainError(error).detail : "" },
        { label: "耗时", value: formatDurationValue(durationMs) },
      ],
      rawEvents,
      occurredAt,
      durationMs,
    });
  }

  if (toolName === "playwright_click_tool") {
    const locator = stringFromRecord(input, "locator") || firstRecordValue(input);
    const explanation = error ? explainError(error) : null;
    return createReadableToolCard({
      event,
      existing,
      kind: "click",
      title: error ? "点击失败" : "点击元素",
      summary: error ? explanation?.reason || "点击元素失败。" : `点击 ${locatorLabel(locator) || "页面元素"}`,
      status: finalStatus,
      fields: [
        { label: "目标", value: locatorLabel(locator) },
        { label: "定位器", value: locator, mono: true },
        {
          label: "结果",
          value: error ? "失败" : status === "running" ? "执行中" : "成功",
          tone: error ? "danger" : "success",
        },
        { label: "原因", value: explanation?.detail || "" },
        { label: "建议", value: explanation?.suggestion || "" },
        { label: "耗时", value: formatDurationValue(durationMs) },
      ],
      rawEvents,
      occurredAt,
      durationMs,
    });
  }

  if (toolName === "playwright_snap_tool" || toolName === "playwright_extract_elements_tool") {
    const elements = arrayFromRecord(output, "elements");
    const roleCounts = summarizeElementRoles(elements);
    const keyElements = summarizeKeyElements(elements);
    const url = stringFromRecord(output, "url") || stringFromRecord(input, "url");
    const title = stringFromRecord(output, "title");
    return createReadableToolCard({
      event,
      existing,
      kind: "snapshot",
      title: "采集页面快照",
      summary:
        title || compactUrl(url) ? `采集 ${title || compactUrl(url)} 的页面结构` : "采集当前页面结构和可交互元素。",
      status: finalStatus,
      fields: [
        { label: "页面", value: title },
        { label: "URL", value: compactUrl(url), mono: true },
        { label: "发现元素", value: roleCounts },
        { label: "关键元素", value: keyElements },
        {
          label: "结果",
          value: error ? "失败" : status === "running" ? "执行中" : "成功",
          tone: error ? "danger" : "success",
        },
        { label: "原因", value: error ? explainError(error).detail : "" },
        { label: "耗时", value: formatDurationValue(durationMs) },
      ],
      rawEvents,
      occurredAt,
      durationMs,
    });
  }

  if (toolName === "write_page_artifact_tool") {
    const path =
      stringFromRecord(output, "path") || stringFromRecord(input, "path") || stringFromRecord(input, "artifact_path");
    const title =
      stringFromRecord(input, "title") || stringFromRecord(input, "page_title") || stringFromRecord(output, "title");
    return createReadableToolCard({
      event,
      existing,
      kind: "artifact_write",
      title: "写入页面事实",
      summary: path ? `写入 ${path.split("/").pop()}` : "写入页面结构、元素定位器和操作路径。",
      status: finalStatus,
      fields: [
        { label: "页面", value: title || compactUrl(stringFromRecord(input, "url")) },
        { label: "产物", value: path, mono: true },
        { label: "包含", value: "页面结构、元素定位器、操作路径" },
        {
          label: "结果",
          value: error ? "失败" : status === "running" ? "执行中" : "成功",
          tone: error ? "danger" : "success",
        },
        { label: "原因", value: error ? explainError(error).detail : "" },
      ],
      rawEvents,
      occurredAt,
      durationMs,
    });
  }

  if (toolName === "write_todos") {
    const todos = arrayFromRecord(input, "todos");
    const currentTodo = todos.find((todo) => recordString(todo, "status") === "in_progress") ?? todos[0];
    const pendingTodos = todos.filter((todo) => recordString(todo, "status") === "pending").slice(0, 3);
    return createReadableToolCard({
      event,
      existing,
      kind: "todo_update",
      title: "探索计划更新",
      summary: recordString(currentTodo, "content") || "更新探索待办计划。",
      status: finalStatus,
      fields: [
        { label: "当前进行", value: recordString(currentTodo, "content") },
        {
          label: "待处理",
          value: pendingTodos.map((todo, index) => `${index + 1}. ${recordString(todo, "content")}`).join("\n"),
        },
        {
          label: "结果",
          value: error ? "失败" : status === "running" ? "执行中" : "完成",
          tone: error ? "danger" : "success",
        },
      ],
      rawEvents,
      occurredAt,
      durationMs,
      defaultExpanded: false,
    });
  }

  if (toolName === "update_explored_url_tool") {
    const url = stringFromRecord(input, "url") || stringFromRecord(output, "url");
    return createReadableToolCard({
      event,
      existing,
      kind: "url_record",
      title: "记录已探索页面",
      summary: compactUrl(url) ? `记录 ${compactUrl(url)} 已访问` : "记录已探索 URL。",
      status: finalStatus,
      fields: [
        { label: "URL", value: compactUrl(url), mono: true },
        { label: "状态", value: error ? "记录失败" : status === "running" ? "记录中" : "已访问" },
      ],
      rawEvents,
      occurredAt,
      durationMs,
    });
  }

  if (error) {
    return readableErrorCardFromEvent(event, existing);
  }

  return createReadableToolCard({
    event,
    existing,
    kind: toolName === "read_file" ? "debug" : "debug",
    title: toolName === "read_file" ? "加载探索规则" : `执行 ${toolName || "工具调用"}`,
    summary: toolName === "read_file" ? "读取探索规则或定位器最佳实践。" : event.summary,
    status: finalStatus,
    fields: [
      { label: "工具", value: toolName },
      { label: "输入", value: stringValue(payload.input), mono: true },
      { label: "结果", value: status === "running" ? "执行中" : "完成" },
    ],
    rawEvents,
    occurredAt,
    durationMs,
    defaultExpanded: false,
  });
}

function createReadableToolCard({
  durationMs,
  event,
  existing,
  fields,
  kind,
  occurredAt,
  rawEvents,
  status,
  summary,
  title,
  defaultExpanded,
}: {
  durationMs: number | null;
  event: ExplorationMonitorEvent;
  existing?: ReadableExecutionCard;
  fields: ReadableExecutionField[];
  kind: ReadableExecutionCardKind;
  occurredAt: string;
  rawEvents: ExplorationMonitorEvent[];
  status: AgentPlanStatus;
  summary: string;
  title: string;
  defaultExpanded?: boolean;
}): ReadableExecutionCard {
  return {
    id: existing?.id ?? `readable-${event.id}`,
    kind,
    title,
    summary,
    status,
    occurred_at: occurredAt,
    completed_at: status === "running" ? "" : event.occurred_at,
    duration_ms: durationMs,
    fields: fields.filter((field) => field.value),
    raw_events: rawEvents,
    defaultExpanded: defaultExpanded ?? (status === "running" || status === "failed"),
  };
}

function readableErrorCardFromEvent(
  event: ExplorationMonitorEvent,
  existing?: ReadableExecutionCard,
): ReadableExecutionCard {
  const payload = event.payload ?? {};
  const error = stringValue(payload.error || payload.reason || payload.message) || event.summary;
  const explanation = explainError(error);
  return {
    id: existing?.id ?? `readable-${event.id}`,
    kind: "error",
    title: event.type === "run_failed" || event.type === "agent_step_failed" ? "探索中断" : "执行失败",
    summary: explanation.reason,
    status: "failed",
    occurred_at: existing?.occurred_at || event.occurred_at,
    completed_at: event.occurred_at,
    duration_ms: existing ? durationBetween(existing.occurred_at, event.occurred_at) : null,
    fields: [
      { label: "原因", value: explanation.detail || explanation.reason, tone: "danger" },
      { label: "影响", value: explanation.impact },
      { label: "建议", value: explanation.suggestion },
    ].filter((field): field is ReadableExecutionField => Boolean(field.value)),
    raw_events: [...(existing?.raw_events ?? []), event],
    defaultExpanded: true,
  };
}

function readableSummaryCardFromState(
  event: ExplorationMonitorEvent | null,
  detail: ExplorationRunDetail | null,
  run: ExplorationRun | null,
  cards: ReadableExecutionCard[],
): ReadableExecutionCard {
  const sourceRun = run ?? detail?.run ?? null;
  const counts = summarizeExecutionCounts(cards);
  const lastError = [...cards].reverse().find((card) => card.status === "failed");
  const pageCount = detail?.modules.reduce((total, module) => total + module.pages.length, 0) ?? 0;
  const status = normalizeAgentPlanStatus(sourceRun?.status || event?.status || "completed");
  const fields: ReadableExecutionField[] = [
    { label: "入口", value: compactUrl(sourceRun?.environment_site_url || ""), mono: true },
    { label: "范围", value: sourceRun?.scope || "" },
    { label: "执行概况", value: counts },
    { label: "产物结果", value: `页面产物数 ${pageCount}` },
    { label: "失败原因", value: lastError?.summary || "", tone: lastError ? "danger" : "default" },
  ];
  return {
    id: event ? `readable-${event.id}` : "readable-run-summary",
    kind: "run_summary",
    title: `探索结束：${sourceRun?.status ? (statusLabels[sourceRun.status] ?? sourceRun.status) : monitorStepLabel(status)}`,
    summary: sourceRun?.result_summary || event?.summary || "探索任务已结束。",
    status,
    occurred_at: event?.occurred_at || sourceRun?.updated_at || new Date().toISOString(),
    fields: fields.filter((field) => field.value),
    raw_events: event ? [event] : [],
    defaultExpanded: true,
  };
}

function readableDebugCardFromEvent(event: ExplorationMonitorEvent): ReadableExecutionCard {
  return {
    id: `readable-${event.id}`,
    kind: "debug",
    title: event.label,
    summary: event.summary,
    status: event.status,
    occurred_at: event.occurred_at,
    fields: [{ label: "事件类型", value: event.type }],
    raw_events: [event],
  };
}

function isHiddenAgentStreamEvent(streamEvent: string, name: string): boolean {
  if (streamEvent === "on_chat_model_stream" || streamEvent === "on_chain_stream") {
    return true;
  }
  if (streamEvent === "on_chat_model_start") {
    return true;
  }
  if (name === "LangGraph") {
    return true;
  }
  if (/Middleware\./.test(name)) {
    return true;
  }
  if (name === "tools" && (streamEvent === "on_chain_start" || streamEvent === "on_chain_end")) {
    return true;
  }
  if (streamEvent === "on_chain_start" && name === "model") {
    return true;
  }
  return false;
}

function isDebugOnlyMonitorEvent(event: ExplorationMonitorEvent): boolean {
  if (event.type === "run_snapshot") {
    return false;
  }
  return event.type === "agent_stream_event";
}

function parseJsonLikePayload(value: string): Record<string, unknown> {
  if (!value) {
    return {};
  }
  const direct = tryParseJsonObject(value);
  if (direct) {
    return direct;
  }
  const contentMatch = value.match(/content=(['"])([\s\S]*?)\1(?:\s|$)/);
  if (contentMatch) {
    const parsedContent = tryParseJsonObject(contentMatch[2]);
    if (parsedContent) {
      return parsedContent;
    }
  }
  const objectMatch = value.match(/\{[\s\S]*\}/);
  if (objectMatch) {
    const parsedObject = tryParseJsonObject(objectMatch[0]);
    if (parsedObject) {
      return parsedObject;
    }
  }
  return {};
}

function tryParseJsonObject(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function stringFromRecord(record: Record<string, unknown>, key: string): string {
  return stringValue(record[key]);
}

function arrayFromRecord(record: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = record[key];
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    : [];
}

function recordString(value: unknown, key: string): string {
  return value && typeof value === "object" ? stringValue((value as Record<string, unknown>)[key]) : "";
}

function firstRecordValue(record: Record<string, unknown>): string {
  const firstValue = Object.values(record).find((value) => value);
  return stringValue(firstValue);
}

function compactUrl(value: string): string {
  if (!value) {
    return "";
  }
  try {
    const url = new URL(value);
    const searchParams = Array.from(url.searchParams.entries()).slice(0, 3);
    const search = searchParams.length ? `?${searchParams.map(([key, item]) => `${key}=${item}`).join("&")}` : "";
    return `${url.pathname || "/"}${search}`;
  } catch {
    return value.length > 96 ? `${value.slice(0, 93)}...` : value;
  }
}

function locatorLabel(locator: string): string {
  if (!locator) {
    return "";
  }
  const roleName = locator.match(/name:\s*['"]([^'"]+)['"]/);
  if (roleName?.[1]) {
    return roleName[1];
  }
  const refMatch = locator.match(/^[a-zA-Z]+-(.+?)-\d+$/);
  if (refMatch?.[1]) {
    return refMatch[1]
      .split("-")
      .filter((part) => part && !/^\d+$/.test(part))
      .join(" / ");
  }
  return locator.length > 64 ? `${locator.slice(0, 61)}...` : locator;
}

function summarizeElementRoles(elements: Record<string, unknown>[]): string {
  if (!elements.length) {
    return "";
  }
  const roleLabels: Record<string, string> = {
    button: "按钮",
    link: "链接",
    textbox: "输入框",
    checkbox: "复选框",
    tab: "标签",
  };
  const counts = elements.reduce<Record<string, number>>((acc, element) => {
    const role = stringValue(element.role || "generic");
    if (role === "generic") {
      return acc;
    }
    acc[role] = (acc[role] ?? 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([role, count]) => `${roleLabels[role] ?? role} ${count}`)
    .join(" · ");
}

function summarizeKeyElements(elements: Record<string, unknown>[]): string {
  return elements
    .filter((element) => element.visible !== false)
    .map((element) => stringValue(element.name || element.text || element.ref))
    .filter(Boolean)
    .slice(0, 5)
    .join("、");
}

function extractToolError(output: Record<string, unknown>): string {
  return stringValue(output.error);
}

function extractModelName(output: string): string {
  const match = output.match(/['"]model_name['"]:\s*['"]([^'"]+)['"]/);
  return match?.[1] ?? "";
}

function extractFinishReason(output: string): string {
  const match = output.match(/['"]finish_reason['"]:\s*['"]([^'"]+)['"]/);
  return match?.[1] ?? "";
}

function extractToolNames(output: string): string[] {
  const names = new Set<string>();
  for (const match of output.matchAll(/['"]name['"]:\s*['"]([^'"]+)['"]/g)) {
    if (match[1] && /tool|read_file|write_todos/.test(match[1])) {
      names.add(match[1]);
    }
  }
  for (const match of output.matchAll(
    /\b(playwright_[a-z_]+|write_page_artifact_tool|update_explored_url_tool|write_todos|read_file)\b/g,
  )) {
    names.add(match[1]);
  }
  return Array.from(names);
}

function extractModelIntent(output: string): string {
  const thinkMatch = output.match(/<think>([\s\S]*?)<\/think>/);
  const rawIntent = thinkMatch?.[1] || output.match(/content=(['"])([\s\S]*?)\1/)?.[2] || "";
  return cleanupModelText(rawIntent);
}

function cleanupModelText(value: string): string {
  return value
    .replace(/\\n/g, " ")
    .replace(/\s+/g, " ")
    .replace(/^The user wants me to/i, "准备")
    .trim()
    .slice(0, 160);
}

function explainError(error: string): { reason: string; detail: string; impact: string; suggestion: string } {
  if (/rate_limit_exceeded|429/.test(error)) {
    return {
      reason: "模型配额限制",
      detail: error,
      impact: "探索未完成，后续页面事实和产物可能缺失。",
      suggestion: "等待配额恢复、更换模型，或降低最大页面数后重试。",
    };
  }
  if (/stale_ref|Unknown element id/.test(error)) {
    return {
      reason: "元素引用已失效",
      detail: "当前页面快照中找不到该元素。",
      impact: "本次点击未执行，后续路径可能无法继续。",
      suggestion: "重新采集页面快照后再点击。",
    };
  }
  if (/timeout/i.test(error)) {
    return {
      reason: "操作超时",
      detail: error,
      impact: "目标页面或元素没有在限定时间内返回。",
      suggestion: "检查页面加载、登录状态或放宽等待时间后重试。",
    };
  }
  if (/Not yet implemented/i.test(error)) {
    return {
      reason: "工具未实现或不可用",
      detail: error,
      impact: "该探索动作无法执行。",
      suggestion: "检查工具注册或改用已支持的页面操作。",
    };
  }
  return {
    reason: "执行异常",
    detail: error,
    impact: "当前动作失败，探索结果可能不完整。",
    suggestion: "展开原始事件查看完整输入输出。",
  };
}

function durationBetween(startedAt: string, completedAt: string): number | null {
  const start = Date.parse(startedAt);
  const end = Date.parse(completedAt);
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
}

function summarizeExecutionCounts(cards: ReadableExecutionCard[]): string {
  const counts = cards.reduce(
    (acc, card) => {
      if (card.kind === "navigate") acc.navigate += 1;
      if (card.kind === "click") acc.click += 1;
      if (card.kind === "snapshot") acc.snapshot += 1;
      if (card.kind === "artifact_write") acc.artifact += 1;
      return acc;
    },
    { artifact: 0, click: 0, navigate: 0, snapshot: 0 },
  );
  return `导航 ${counts.navigate} 次 · 点击 ${counts.click} 次 · 快照 ${counts.snapshot} 次 · 写产物 ${counts.artifact} 次`;
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

function buildAgentPlanTasks(detail: ExplorationRunDetail | null, monitor?: ExplorationMonitorState): AgentPlanTask[] {
  if (!detail?.modules?.length) {
    return buildMonitorModuleTasks(monitor);
  }
  const hideEmptyPlanModules = isTerminalStatus(detail.run.status);
  const tasks = detail.modules
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
  return tasks.length ? tasks : buildMonitorModuleTasks(monitor);
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
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [environments, setEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [requirements, setRequirements] = useState<RequirementDocument[]>([]);
  const [requirementLoading, setRequirementLoading] = useState(false);
  const [explorationForm, setExplorationForm] = useState<ExplorationForm>(emptyExplorationForm);
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
      explorationMode: run.exploration_mode,
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
      const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${run.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          environment_id: explorationForm.environmentId,
          requirement_doc_id: explorationForm.requirementDocId,
          exploration_mode: explorationForm.explorationMode,
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
        path: `/page-exploration/runs/${run.id}`,
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
  const agentPlanTasks = buildAgentPlanTasks(activeDetail, monitor);
  return (
    <PageShell
      breadcrumbs={["项目", projectName, "探索", run?.title ?? "探索任务"]}
      description="查看探索任务运行概览、执行日志和探索报告。"
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
              <Button disabled={!canEdit} onClick={openEditDialog} size="sm" variant="outline">
                <Pencil className="size-4" />
                编辑
              </Button>
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
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}
      {activeTab === "探索概览" ? (
        <ExplorationModuleProgressPanel
          agentPlanTasks={agentPlanTasks}
          isUnsupportedArtifact={isUnsupportedArtifact}
          loading={loading}
          detail={activeDetail}
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
              <ExplorationModeSwitch
                onChange={(explorationMode) => setExplorationForm((current) => ({ ...current, explorationMode }))}
                value={explorationForm.explorationMode}
              />
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
              <FieldLabel htmlFor="exploration-goal">
                {explorationForm.explorationMode === "autonomous" ? "补充关注点" : "探索目标"}
              </FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-goal"
                onChange={(event) => setExplorationForm((current) => ({ ...current, goal: event.target.value }))}
                placeholder={
                  explorationForm.explorationMode === "autonomous"
                    ? explorationPlaceholders.autonomousGoal
                    : explorationPlaceholders.goal
                }
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
      <div className="min-w-0 flex-1 truncate text-destructive">探索任务加载失败：{error}。</div>
      <Button aria-label="关闭探索失败信息" onClick={onClose} size="icon-xs" type="button" variant="ghost">
        <X className="size-4" />
      </Button>
    </div>
  );
}

function ExplorationModuleProgressPanel({
  agentPlanTasks,
  isUnsupportedArtifact,
  loading,
  detail,
  monitor,
  onRestart,
  restarting,
  run,
  unsupportedArtifactReason,
}: {
  agentPlanTasks: AgentPlanTask[];
  isUnsupportedArtifact: boolean;
  loading: boolean;
  detail: ExplorationRunDetail | null;
  monitor: ExplorationMonitorState;
  onRestart: () => Promise<void> | void;
  restarting: boolean;
  run: ExplorationRun | null;
  unsupportedArtifactReason: string;
}) {
  const completedCount = agentPlanTasks.filter((task) => task.status === "completed").length;
  const moduleCount = agentPlanTasks.length;
  const moduleProgress = moduleCount > 0 ? Math.round((completedCount / moduleCount) * 100) : 0;
  const activeStep = monitor.steps.find((step) => step.status === "running" || step.status === "in-progress");

  return (
    <ShellSection className="flex min-h-0 min-w-0 flex-1 lg:col-span-2">
      <div className="grid min-h-[480px] flex-1 gap-4 lg:min-h-0 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="min-h-0 min-w-0 overflow-y-auto rounded-lg border bg-muted/10 p-2">
          {!loading ? <ExplorationMapFocus detail={detail} monitor={monitor} run={run} /> : null}
          {loading ? (
            <div className="grid min-h-[360px] place-items-center rounded-md bg-background/70 p-6 text-center text-muted-foreground text-sm">
              探索进度加载中...
            </div>
          ) : isUnsupportedArtifact ? (
            <UnsupportedArtifactNotice
              onRestart={onRestart}
              reason={unsupportedArtifactReason}
              restarting={restarting}
            />
          ) : agentPlanTasks.length > 0 ? (
            <ExplorationModuleIndex
              completedCount={completedCount}
              moduleCount={moduleCount}
              moduleProgress={moduleProgress}
              tasks={agentPlanTasks}
            />
          ) : (
            <ExplorationModuleEmptyState activeStep={activeStep} monitor={monitor} run={run} />
          )}
        </div>
        <ExplorationRealtimeStreamPanel className="h-full" monitor={monitor} run={run} streamDetail={detail} />
      </div>
    </ShellSection>
  );
}

function ExplorationMapFocus({
  detail,
  monitor,
  run,
}: {
  detail: ExplorationRunDetail | null;
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
}) {
  const activeStep = monitor.steps.find((step) => step.status === "running" || step.status === "in-progress");
  const firstModule = detail?.modules?.[0];
  const title = activeStep?.module_name || firstModule?.module_name || monitor.plan?.modules[0] || "主探索模块";
  const summary =
    activeStep?.message ||
    activeStep?.description ||
    firstModule?.completion_summary ||
    detail?.run.result_summary ||
    monitor.plan?.scope_summary ||
    run?.scope ||
    "等待页面事实生成。";
  const status = activeStep
    ? activeStep.status
    : normalizeAgentPlanStatus(firstModule?.completion_status || run?.status || "pending");

  return (
    <div className="mb-2 rounded-md border bg-background p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] text-muted-foreground">当前焦点</div>
          <div className="mt-1 truncate font-medium text-sm" title={title}>
            {title}
          </div>
        </div>
        <StatusBadge tone={monitorStepTone(status)}>{monitorStepLabel(status)}</StatusBadge>
      </div>
      <div className="mt-2 line-clamp-2 text-muted-foreground text-xs" title={summary}>
        {summary}
      </div>
      {activeStep?.action_type ? (
        <div className="mt-2 inline-flex max-w-full items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700 dark:bg-blue-500/10 dark:text-blue-200">
          <Activity className="size-3 shrink-0" />
          <span className="truncate">{activeStep.action_type}</span>
        </div>
      ) : null}
    </div>
  );
}

function ExplorationModuleIndex({
  completedCount,
  moduleCount,
  moduleProgress,
  tasks,
}: {
  completedCount: number;
  moduleCount: number;
  moduleProgress: number;
  tasks: AgentPlanTask[];
}) {
  return (
    <div className="space-y-2">
      <div className="rounded-md border bg-background p-3">
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="text-muted-foreground">模块完成度</span>
          <span className="font-semibold text-foreground">{moduleCount ? `${moduleProgress}%` : "-"}</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${moduleCount ? moduleProgress : 0}%` }} />
        </div>
        <div className="mt-2 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">模块</span>
          <span className="font-semibold text-foreground">
            {moduleCount ? `${completedCount}/${moduleCount}` : "-"}
          </span>
        </div>
      </div>
      {tasks.map((task) => {
        const pages = task.subtasks ?? [];
        const pageCount = pages.length;
        const failedPages = pages.filter((page) => page.status === "failed" || page.status === "blocked").length;
        const activePages = pages.filter((page) =>
          ["queued", "running", "in-progress", "stopping"].includes(page.status),
        ).length;
        return (
          <div className="rounded-md border bg-background p-3" key={task.id}>
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate font-medium text-sm" title={task.title}>
                  {task.title}
                </div>
                {task.description ? (
                  <div className="mt-1 line-clamp-2 text-muted-foreground text-xs" title={task.description}>
                    {task.description}
                  </div>
                ) : null}
              </div>
              <StatusBadge tone={monitorStepTone(task.status)}>{monitorStepLabel(task.status)}</StatusBadge>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
              <span className="rounded bg-muted px-1.5 py-0.5">{pageCount ? `${pageCount} 页面` : "暂无页面"}</span>
              {activePages ? (
                <span className="rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">{activePages} 进行中</span>
              ) : null}
              {failedPages ? (
                <span className="rounded bg-red-50 px-1.5 py-0.5 text-red-700">{failedPages} 异常</span>
              ) : null}
              {task.meta?.map((item) => (
                <span className="rounded bg-muted px-1.5 py-0.5" key={item}>
                  {item}
                </span>
              ))}
            </div>
            {pages.length ? (
              <div className="mt-3 space-y-1 border-muted border-l pl-3">
                {pages.slice(0, 8).map((page) => (
                  <div className="min-w-0 rounded px-2 py-1 hover:bg-muted/60" key={page.id}>
                    <div className="flex min-w-0 items-center gap-2">
                      <MonitorStatusIcon status={page.status} />
                      <span className="truncate text-xs" title={page.title}>
                        {page.title}
                      </span>
                    </div>
                    {page.description ? (
                      <div
                        className="mt-0.5 line-clamp-1 pl-5 text-[11px] text-muted-foreground"
                        title={page.description}
                      >
                        {page.description}
                      </div>
                    ) : null}
                  </div>
                ))}
                {pages.length > 8 ? (
                  <div className="pl-2 text-[11px] text-muted-foreground">还有 {pages.length - 8} 个页面</div>
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function ExplorationModuleEmptyState({
  activeStep,
  monitor,
  run,
}: {
  activeStep?: ExplorationMonitorStep;
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
}) {
  const pending = run?.status === "pending";
  const hasEvents = monitor.events.length > 0 || monitor.steps.length > 0;
  const title = pending ? "等待开始探索" : hasEvents ? "正在建立探索地图" : "尚未形成页面产物";
  const description = pending
    ? "点击「开始探索」后会在这里生成模块轨道。"
    : hasEvents
      ? "已收到实时执行事件，页面事实写入后会自动挂到模块下面。"
      : "实时流启动后会先显示当前模块，页面产物生成后展示页面覆盖。";
  return (
    <div className="grid min-h-full place-items-center rounded-md bg-background/70 p-6 text-center">
      <div className="max-w-sm space-y-2">
        <div className="mx-auto flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <ListChecks className="size-4" />
        </div>
        <div className="font-medium text-sm">{title}</div>
        <p className="text-muted-foreground text-xs">{description}</p>
        {activeStep ? (
          <div className="mx-auto mt-3 max-w-full rounded-md border bg-muted/20 px-3 py-2 text-left text-xs">
            <div className="text-muted-foreground">当前动作</div>
            <div className="mt-1 truncate font-medium" title={activeStep.description || activeStep.action_type}>
              {activeStep.description || activeStep.action_type}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ExplorationRealtimeStreamPanel({
  className = "",
  monitor,
  run,
  streamDetail,
}: {
  className?: string;
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
  streamDetail: ExplorationRunDetail | null;
}) {
  const phaseLabel = monitorPhaseLabel(monitor.phase, run?.status);
  const events = monitor.events;
  const readableCards = useMemo(
    () => buildReadableExecutionCards(events, streamDetail, run),
    [events, run, streamDetail],
  );
  const debugEventCount = Math.max(
    events.length - readableCards.reduce((total, card) => total + card.raw_events.length, 0),
    0,
  );
  const latestEventKey = useMemo(() => {
    const latestCard = readableCards.at(-1);
    if (!latestCard) {
      return "";
    }
    return JSON.stringify([
      readableCards.length,
      latestCard.id,
      latestCard.status,
      latestCard.summary,
      latestCard.completed_at || latestCard.occurred_at,
      latestCard.raw_events.length,
    ]);
  }, [readableCards]);
  const eventListRef = useRef<HTMLDivElement | null>(null);
  const shouldFollowBottomRef = useRef(true);
  const previousLatestEventKeyRef = useRef("");
  const [unreadEventCount, setUnreadEventCount] = useState(0);

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
    <Card
      className={`min-h-0 min-w-0 overflow-hidden border-blue-100/80 bg-background dark:border-blue-500/20 ${className}`}
      size="sm"
    >
      <CardHeader className="border-b bg-blue-50/50 pb-3 dark:bg-blue-500/5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Activity className="size-4" />
              实时执行流
            </CardTitle>
            <CardDescription className="text-xs">关键动作摘要，原始事件保留在卡片调试区</CardDescription>
          </div>
          <StatusBadge tone={monitorPhaseTone(monitor.phase, run?.status)}>{phaseLabel}</StatusBadge>
        </div>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-2">
          <ReadableExecutionOverview cards={readableCards} debugEventCount={debugEventCount} run={run} />
          <div className="flex items-center justify-between text-xs">
            <div className="font-medium text-muted-foreground">关键执行流</div>
            <div className="text-muted-foreground">
              {readableCards.length ? `${readableCards.length} 张卡片 · 原始 ${events.length} 条` : "等待事件"}
            </div>
          </div>
          {readableCards.length ? (
            <div
              className="min-h-0 flex-1 space-y-2 overflow-y-auto rounded-md border bg-muted/20 p-2"
              onScroll={handleEventListScroll}
              ref={eventListRef}
            >
              {readableCards.map((card) => (
                <ReadableExecutionCardView card={card} key={card.id} />
              ))}
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
            <div className="grid min-h-0 flex-1 place-items-center rounded-md bg-muted/20 p-4 text-center text-muted-foreground text-sm">
              {isActiveStatus(run?.status ?? "") ? "等待后端推送探索事件。" : "开始探索后会在这里显示实时执行流。"}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ReadableExecutionOverview({
  cards,
  debugEventCount,
  run,
}: {
  cards: ReadableExecutionCard[];
  debugEventCount: number;
  run: ExplorationRun | null;
}) {
  const counts = summarizeExecutionCounts(cards);
  const latestError = cards.find((card) => card.status === "failed");
  const latestRunning = cards.find((card) => card.status === "running" || card.status === "in-progress");
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={monitorPhaseTone("", run?.status)}>
          {run?.status ? (statusLabels[run.status] ?? run.status) : "待开始"}
        </StatusBadge>
        {run?.goal ? <span className="min-w-0 flex-1 truncate text-muted-foreground">目标：{run.goal}</span> : null}
      </div>
      <div className="mt-2 grid gap-1 text-muted-foreground">
        {run?.environment_site_url ? (
          <div className="truncate">入口：{compactUrl(run.environment_site_url)}</div>
        ) : null}
        <div className="truncate">关键动作：{counts}</div>
        {latestError ? (
          <div className="text-red-600 dark:text-red-400">最后异常：{latestError.summary}</div>
        ) : latestRunning ? (
          <div>
            当前动作：{latestRunning.title}，{latestRunning.summary}
          </div>
        ) : debugEventCount ? (
          <div>已隐藏调试事件：{debugEventCount} 条，可在卡片原始事件中查看关键输入输出。</div>
        ) : null}
      </div>
    </div>
  );
}

function ReadableExecutionCardView({ card }: { card: ReadableExecutionCard }) {
  const [expanded, setExpanded] = useState(Boolean(card.defaultExpanded));
  const hasRawEvents = card.raw_events.length > 0;
  return (
    <div className="overflow-hidden rounded-md border bg-background text-sm">
      <button
        className="flex w-full min-w-0 items-start gap-2 px-3 py-2 text-left transition-colors hover:bg-blue-50/60 dark:hover:bg-blue-500/10"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <span className="mt-0.5 shrink-0 text-muted-foreground">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </span>
        <MonitorStatusIcon status={card.status} />
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="truncate font-medium">{card.title}</span>
            <StatusBadge tone={monitorStepTone(card.status)}>{monitorStepLabel(card.status)}</StatusBadge>
            {card.chips?.slice(0, 3).map((chip) => (
              <span className="rounded border bg-muted/30 px-1.5 py-0.5 text-[11px] text-muted-foreground" key={chip}>
                {chip}
              </span>
            ))}
          </span>
          <span className="mt-1 line-clamp-2 block text-muted-foreground text-xs" title={card.summary}>
            {card.summary}
          </span>
        </span>
        <span className="shrink-0 pt-0.5 text-[11px] text-muted-foreground">{formatDateTime(card.occurred_at)}</span>
      </button>
      {expanded ? (
        <div className="space-y-3 border-t bg-muted/10 px-3 py-3">
          <div className="grid gap-2 md:grid-cols-2">
            {card.fields.map((field) => (
              <ReadableExecutionFieldRow field={field} key={`${field.label}-${field.value}`} />
            ))}
          </div>
          {card.status === "running" || card.status === "in-progress" ? (
            <div className="flex items-center gap-2 text-muted-foreground text-xs">
              <Loader2 className="size-3 animate-spin" />
              执行中...
            </div>
          ) : null}
          {hasRawEvents ? <RawExecutionEvents events={card.raw_events} /> : null}
        </div>
      ) : null}
    </div>
  );
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

function RawExecutionEvents({ events }: { events: ExplorationMonitorEvent[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded-md border bg-background">
      <button
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-muted-foreground text-xs hover:bg-muted/40"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <span>原始事件 / 输入输出 / 调试信息（{events.length}）</span>
        {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
      </button>
      {expanded ? (
        <pre className="max-h-64 overflow-auto border-t p-2 text-[11px] leading-relaxed">
          {JSON.stringify(
            events.map((event) => ({
              type: event.type,
              occurred_at: event.occurred_at,
              status: event.status,
              payload: event.payload,
            })),
            null,
            2,
          )}
        </pre>
      ) : null}
    </div>
  );
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

function formatDurationValue(value: unknown): string {
  const duration = Number(value);
  return Number.isFinite(duration) && duration >= 0 ? `${duration}ms` : "";
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
