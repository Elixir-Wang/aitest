import { CheckCircle2, Circle, ListChecks, Loader2, XCircle, AlertTriangle, MinusCircle } from "lucide-react";
import type { AgentPlanStatus } from "@/components/ui/agent-plan";

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
    steps: ExplorationMonitorPlanStep[];
  } | null;
  steps: ExplorationMonitorStep[];
  events: ExplorationMonitorEvent[];
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

const phaseLabels: Record<string, string> = {
  idle: "空闲",
  planning: "规划中",
  planned: "已规划",
  replanning: "重新规划",
  executing: "执行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

const actionTypeLabels: Record<string, string> = {
  navigate: "导航",
  click: "点击",
  fill: "填写",
  observe: "观察",
  wait: "等待",
  event: "事件",
};

function StepStatusIcon({ status }: { status: AgentPlanStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="size-4 text-green-600" />;
    case "running":
    case "in-progress":
      return <Loader2 className="size-4 animate-spin text-blue-600" />;
    case "failed":
      return <XCircle className="size-4 text-red-600" />;
    case "cancelled":
      return <MinusCircle className="size-4 text-muted-foreground" />;
    case "partial":
      return <AlertTriangle className="size-4 text-amber-600" />;
    case "blocked":
      return <AlertTriangle className="size-4 text-orange-600" />;
    default:
      return <Circle className="size-4 text-muted-foreground" />;
  }
}

function formatTime(timestamp: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function ExplorationTaskInfoPanel({
  monitor,
  loading,
}: {
  monitor: ExplorationMonitorState;
  loading: boolean;
}) {
  const { phase, plan, steps, events } = monitor;
  const hasSteps = steps.length > 0;

  return (
    <div className="grid min-h-[600px] gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      {/* 左侧：探索计划和步骤列表 */}
      <aside className="flex flex-col gap-4 rounded-lg border bg-muted/20 p-4">
        {/* 计划概览 */}
        {plan ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <ListChecks className="size-5 text-primary" />
              <h3 className="font-semibold text-base">探索计划</h3>
            </div>
            <div className="space-y-2 rounded-lg border bg-background p-3 text-sm">
              {plan.goal_summary ? (
                <div>
                  <div className="font-medium text-muted-foreground text-xs">目标</div>
                  <div className="mt-1">{plan.goal_summary}</div>
                </div>
              ) : null}
              {plan.scope_summary ? (
                <div className="border-t pt-2">
                  <div className="font-medium text-muted-foreground text-xs">范围</div>
                  <div className="mt-1">{plan.scope_summary}</div>
                </div>
              ) : null}
              {plan.strategy ? (
                <div className="border-t pt-2">
                  <div className="font-medium text-muted-foreground text-xs">策略</div>
                  <div className="mt-1">{plan.strategy}</div>
                </div>
              ) : null}
              {plan.estimated_duration_minutes ? (
                <div className="border-t pt-2">
                  <div className="font-medium text-muted-foreground text-xs">预计时长</div>
                  <div className="mt-1">{plan.estimated_duration_minutes} 分钟</div>
                </div>
              ) : null}
              {plan.total_steps > 0 ? (
                <div className="border-t pt-2">
                  <div className="font-medium text-muted-foreground text-xs">步骤数</div>
                  <div className="mt-1">{plan.total_steps} 个步骤</div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {/* 步骤列表 */}
        <div className="flex-1 space-y-3">
          <h3 className="font-semibold text-sm">执行步骤</h3>
          {loading && !hasSteps ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
              <Loader2 className="mr-2 size-4 animate-spin" />
              加载中...
            </div>
          ) : !hasSteps ? (
            <div className="rounded-lg border bg-background p-4 text-center text-muted-foreground text-sm">
              暂无步骤信息
            </div>
          ) : (
            <div className="space-y-2 overflow-auto">
              {steps.map((step) => (
                <ExplorationStepCard key={step.step_id} step={step} />
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* 右侧：实时执行监控 */}
      <main className="flex flex-col gap-4 rounded-lg border bg-background p-4">
        {/* 阶段指示器 */}
        <div className="flex items-center justify-between border-b pb-3">
          <h3 className="font-semibold text-base">实时执行监控</h3>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">当前阶段：</span>
            <span className="font-medium">{phaseLabels[phase] || phase}</span>
            {phase === "planning" || phase === "executing" ? (
              <Loader2 className="ml-1 size-4 animate-spin text-blue-600" />
            ) : null}
          </div>
        </div>

        {/* 事件流 */}
        <div className="flex-1 space-y-2 overflow-auto">
          {loading && events.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              <Loader2 className="mr-2 size-4 animate-spin" />
              等待事件流...
            </div>
          ) : events.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
              暂无事件记录
            </div>
          ) : (
            events.map((event) => <ExplorationEventCard key={event.id} event={event} />)
          )}
        </div>
      </main>
    </div>
  );
}

function ExplorationStepCard({ step }: { step: ExplorationMonitorStep }) {
  const isExpanded = step.status === "running" || step.status === "in-progress" || step.status === "failed";

  return (
    <div className="rounded-lg border bg-background p-3 transition-colors hover:bg-muted/30">
      <div className="flex items-start gap-2">
        <div className="mt-0.5 shrink-0">
          <StepStatusIcon status={step.status} />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-medium text-sm">#{step.step_number}</span>
            <span className="truncate text-sm">{step.description}</span>
          </div>
          {step.module_name ? (
            <div className="text-muted-foreground text-xs">模块: {step.module_name}</div>
          ) : null}
          {isExpanded && step.target_description ? (
            <div className="text-muted-foreground text-xs">目标: {step.target_description}</div>
          ) : null}
          {isExpanded && step.action_type ? (
            <div className="text-muted-foreground text-xs">
              动作: {actionTypeLabels[step.action_type] || step.action_type}
            </div>
          ) : null}
          {step.message ? <div className="text-xs">{step.message}</div> : null}
          {step.error ? <div className="text-red-600 text-xs">错误: {step.error}</div> : null}
        </div>
      </div>
    </div>
  );
}

function ExplorationEventCard({ event }: { event: ExplorationMonitorEvent }) {
  const statusColor = {
    completed: "text-green-600",
    running: "text-blue-600",
    failed: "text-red-600",
    cancelled: "text-muted-foreground",
    partial: "text-amber-600",
    blocked: "text-orange-600",
    pending: "text-muted-foreground",
    stopping: "text-orange-600",
    "in-progress": "text-blue-600",
  }[event.status];

  return (
    <div className="rounded-lg border bg-muted/10 p-3 text-sm">
      <div className="flex items-start gap-2">
        <div className={`mt-0.5 shrink-0 ${statusColor}`}>
          <StepStatusIcon status={event.status} />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-muted-foreground text-xs">{formatTime(event.occurred_at)}</span>
            <span className={`rounded-md bg-primary/10 px-2 py-0.5 font-medium text-xs ${statusColor}`}>
              {event.label}
            </span>
          </div>
          {event.summary ? <div className="text-sm">{event.summary}</div> : null}
          {event.display ? <ReadableExecutionDisplayCard display={event.display} /> : null}
        </div>
      </div>
    </div>
  );
}

function ReadableExecutionDisplayCard({ display }: { display: ReadableExecutionDisplay }) {
  return (
    <div className="mt-2 rounded-md border bg-background p-2">
      <div className="font-medium text-sm">{display.title}</div>
      {display.summary ? <div className="mt-1 text-muted-foreground text-xs">{display.summary}</div> : null}
      {display.fields && display.fields.length > 0 ? (
        <div className="mt-2 space-y-1">
          {display.fields.map((field, index) => (
            <div key={index} className="grid grid-cols-[80px_1fr] gap-2 text-xs">
              <div className="text-muted-foreground">{field.label}:</div>
              <div
                className={`break-all ${field.mono ? "font-mono" : ""} ${
                  field.tone === "success"
                    ? "text-green-600"
                    : field.tone === "warning"
                      ? "text-amber-600"
                      : field.tone === "danger"
                        ? "text-red-600"
                        : ""
                }`}
              >
                {field.value}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {display.chips && display.chips.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {display.chips.map((chip, index) => (
            <span key={index} className="rounded-md bg-muted px-2 py-0.5 text-xs">
              {chip}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
