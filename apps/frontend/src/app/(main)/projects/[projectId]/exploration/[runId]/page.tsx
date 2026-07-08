"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { AlertTriangle, ArrowLeft, Play, RefreshCw, Square, X } from "lucide-react";
import { toast } from "sonner";

import { ExplorationTaskInfoPanel } from "@/components/ai-testing/exploration-task-info-panel";
import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import type { AgentPlanStatus } from "@/components/ui/agent-plan";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { API_BASE_URL, apiAuthHeaders, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError as reportApiError } from "@/lib/error-feedback";
import type {
  ExplorationMonitorEvent,
  ExplorationMonitorPlanStep,
  ExplorationMonitorState,
  ExplorationMonitorStep,
  ExplorationReport,
  ExplorationRun,
  ExplorationRunDetail,
  ExplorationStep,
  ExplorationStreamEvent,
  ReadableExecutionDisplay,
  ReadableExecutionDisplayKind,
  ReadableExecutionField,
} from "@/lib/exploration-types";

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
    setters.setMonitor((current) => mergeMonitorSnapshot(current, snapshot));
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
    return mergeMonitorSnapshot(current, event.payload as ExplorationRunDetail);
  }
  const payload = event.payload as Record<string, unknown>;
  let next: ExplorationMonitorState = {
    ...current,
    phase: monitorPhaseFromEvent(event.type, current.phase),
  };

  if (event.type === "planning_completed" || event.type === "agent_plan_updated") {
    const steps = event.type === "agent_plan_updated" ? normalizeMonitorPlanSteps(payload.plan_steps) : [];
    next = {
      ...next,
      plan: {
        plan_id: stringValue(payload.plan_id) || next.plan?.plan_id || "",
        goal_summary: stringValue(payload.goal_summary) || next.plan?.goal_summary || "",
        scope_summary: stringValue(payload.scope_summary) || next.plan?.scope_summary || "",
        strategy: stringValue(payload.strategy) || next.plan?.strategy || "Agent 待办计划",
        modules: arrayOfStrings(payload.modules).length ? arrayOfStrings(payload.modules) : next.plan?.modules || [],
        estimated_duration_minutes:
          numberOrNull(payload.estimated_duration_minutes) ?? next.plan?.estimated_duration_minutes ?? null,
        risk_assessment: stringValue(payload.risk_assessment) || next.plan?.risk_assessment || "",
        success_criteria: arrayOfStrings(payload.success_criteria).length
          ? arrayOfStrings(payload.success_criteria)
          : next.plan?.success_criteria || [],
        total_steps: Number(payload.total_steps || steps.length || 0),
        steps,
      },
      steps: event.type === "agent_plan_updated" ? mergeMonitorPlanSteps(next.steps, steps) : next.steps,
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

function mergeMonitorSnapshot(current: ExplorationMonitorState, detail: ExplorationRunDetail): ExplorationMonitorState {
  const snapshot = finalizeRunningMonitorSteps(monitorFromRunDetail(detail), detail.run.status);
  if (!hasMonitorProgress(current)) {
    return snapshot;
  }
  if (!hasMonitorProgress(snapshot)) {
    return finalizeRunningMonitorSteps(
      {
        ...current,
        phase: monitorPhaseFromRunStatus(detail.run.status),
        events: mergeMonitorEvents(current.events, snapshot.events),
      },
      detail.run.status,
    );
  }
  return finalizeRunningMonitorSteps(
    {
      ...snapshot,
      plan: snapshot.plan ?? current.plan,
      steps: snapshot.steps.length ? mergeMonitorSteps(current.steps, snapshot.steps) : current.steps,
      events: mergeMonitorEvents(current.events, snapshot.events),
    },
    detail.run.status,
  );
}

function hasMonitorProgress(monitor: ExplorationMonitorState): boolean {
  return Boolean(monitor.plan) || monitor.steps.length > 0 || monitor.events.length > 0;
}

function mergeMonitorSteps(
  current: ExplorationMonitorStep[],
  incoming: ExplorationMonitorStep[],
): ExplorationMonitorStep[] {
  return incoming
    .reduce((steps, step) => upsertMonitorStep(steps, step), current)
    .sort((a, b) => a.step_number - b.step_number);
}

function mergeMonitorEvents(
  current: ExplorationMonitorEvent[],
  incoming: ExplorationMonitorEvent[],
): ExplorationMonitorEvent[] {
  const seen = new Set<string>();
  const merged: ExplorationMonitorEvent[] = [];
  for (const event of [...incoming, ...current]) {
    const key = event.id;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    merged.push(event);
  }
  return merged;
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
  if (runStatus === "completed") {
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
  if (runStatus === "completed") {
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

function emptyRunDetail(run: ExplorationRun): ExplorationRunDetail {
  return {
    run,
    artifact_schema_version: 0,
    unsupported_artifact: false,
    unsupported_reason: "",
    timeline_events: [],
    modules: [],
  };
}

function monitorFromRunDetail(detail: ExplorationRunDetail): ExplorationMonitorState {
  const detailSteps = monitorStepsFromDetail(detail);
  const persistedPlanSteps = monitorStepsFromPersistedPlanEvents(detail);
  const steps = detailSteps.length ? mergeMonitorSteps(persistedPlanSteps, detailSteps) : persistedPlanSteps;
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

function monitorStepsFromPersistedPlanEvents(detail: ExplorationRunDetail): ExplorationMonitorStep[] {
  const timelineEvents = Array.isArray(detail.timeline_events) ? detail.timeline_events : [];
  let latestSteps: ExplorationMonitorStep[] = [];
  for (const event of timelineEvents) {
    if (event.type !== "agent_plan_updated") {
      continue;
    }
    const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
    const rawPlanSteps = Array.isArray(payload.plan_steps) ? payload.plan_steps : [];
    const planSteps = normalizeMonitorPlanSteps(rawPlanSteps);
    if (!planSteps.length) {
      continue;
    }
    const occurredAt = stringValue(event.occurred_at || event.timestamp);
    latestSteps = planSteps.map((planStep, index) => {
      const rawPlanStep = rawPlanSteps[index] && typeof rawPlanSteps[index] === "object" ? rawPlanSteps[index] : {};
      const status = normalizeAgentPlanStatus(stringValue((rawPlanStep as Record<string, unknown>).status));
      return {
        ...emptyMonitorStep(planStep),
        status,
        total_steps: planSteps.length,
        completed_at: status === "completed" ? occurredAt : "",
      };
    });
  }
  return latestSteps;
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
    steps: [],
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
  return events;
}

function persistedMonitorEventsFromDetail(detail: ExplorationRunDetail): ExplorationMonitorEvent[] {
  const timelineEvents = Array.isArray(detail.timeline_events) ? detail.timeline_events : [];
  const events: ExplorationMonitorEvent[] = [];
  for (const [index, event] of timelineEvents.entries()) {
    if (!event || typeof event.type !== "string") {
      continue;
    }
    const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
    const streamEvent = stringValue(payload.event);
    const streamName = stringValue(payload.name);
    const display = readableDisplayFromPayload(event as unknown as Record<string, unknown>);
    if (!display) {
      continue;
    }
    const summary =
      stringValue(payload.message) ||
      stringValue(payload.error) ||
      display.summary ||
      streamName ||
      streamEvent ||
      event.type;
    events.push({
      id: `persisted-${event.event_id || index}`,
      type: event.type,
      label: logTypeLabels[event.type] ?? event.type,
      summary,
      occurred_at: stringValue(event.occurred_at || event.timestamp) || detail.run.updated_at,
      status: persistedMonitorEventStatus(event.type, payload),
      payload,
      display,
    });
  }
  return events;
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
    status: normalizeAgentPlanStatus(stringValue(payload.status)) || monitorStepStatusFromEvent(eventType),
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
  if (eventType === "step_failed" || eventType === "step_skipped") return "failed";
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
  // Use the backend's persisted timeline_event_id so the live event dedupes
  // against the same event later arriving via run_snapshot (which uses
  // `persisted-${event_id}` as the id). Fallback to a random id only if the
  // backend did not provide one (e.g. lifecycle events outside the streaming
  // loop).
  const stableId = stringValue(event.timeline_event_id);
  return {
    id: stableId ? `persisted-${stableId}` : `${event.type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
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
  if (eventType.includes("completed") || eventType === "agent_plan_updated") return "completed";
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

function normalizeExplorationRunDetail(data: ExplorationRunDetail): ExplorationRunDetail {
  return data;
}

function normalizeAgentPlanStatus(status: string): AgentPlanStatus {
  if (status === "running" || status === "queued" || status === "in-progress" || status === "in_progress") {
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
  return ["completed", "blocked", "cancelled", "interrupted", "failed"].includes(status);
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
        setMonitor((current) => mergeMonitorSnapshot(current, normalizedData));
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
      const emptyDetail = emptyRunDetail(updated);
      setRun(updated);
      setDetail(emptyDetail);
      setStreamDetail(emptyDetail);
      setMonitor(emptyMonitorState);
      setReport(null);
      setReportError("");
      setReportPrefetchedForRunId("");
      setError("");
      setFailureVisible(true);
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
    ? ["pending", "completed", "blocked", "cancelled", "interrupted", "failed"].includes(run.status)
    : false;
  const canStop = run ? stoppableStatuses.has(run.status) : false;
  const activeDetail = streamDetail ?? detail;
  const isUnsupportedArtifact = Boolean(activeDetail?.unsupported_artifact);
  const unsupportedArtifactReason = activeDetail?.unsupported_reason || "历史产物格式不支持新版详情，请重新探索。";
  const templateLabel = run?.exploration_mode === "goal" ? "目标探索模板" : "自主探索";
  return (
    <PageShell
      breadcrumbs={[
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "探索", href: "/exploration" },
        ...(run ? [{ label: run.title }] : []),
      ]}
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
          runStatus={run?.status ?? "pending"}
          restarting={starting}
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
            <DialogDescription>停止后将终止当前浏览器探索进程，已生成的日志和页面事实会保留。</DialogDescription>
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
  runStatus,
  restarting,
  unsupportedArtifactReason,
}: {
  isUnsupportedArtifact: boolean;
  loading: boolean;
  monitor: ExplorationMonitorState;
  onRestart: () => Promise<void> | void;
  runStatus: string;
  restarting: boolean;
  unsupportedArtifactReason: string;
}) {
  // 如果是不支持的产物格式，显示提示
  if (isUnsupportedArtifact) {
    return (
      <ShellSection>
        <UnsupportedArtifactNotice onRestart={onRestart} reason={unsupportedArtifactReason} restarting={restarting} />
      </ShellSection>
    );
  }

  // 使用新的双栏布局组件
  return (
    <ShellSection>
      <ExplorationTaskInfoPanel monitor={monitor} loading={loading} status={normalizeAgentPlanStatus(runStatus)} />
    </ShellSection>
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
