import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  ListChecks,
  Loader2,
  MinusCircle,
  XCircle,
} from "lucide-react";

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

type ExecutionTranscriptBlock = {
  id: string;
  type: "message" | "tool";
  title: string;
  output: string;
  fields: ReadableExecutionField[];
  chips: string[];
  status: AgentPlanStatus;
  occurredAt: string;
  completedAt: string;
  toolName: string;
  defaultOpen: boolean;
};

const actionTypeLabels: Record<string, string> = {
  navigate: "导航",
  click: "点击",
  fill: "填写",
  observe: "观察",
  wait: "等待",
  event: "事件",
};

const stepStatusIconByStatus: Partial<Record<AgentPlanStatus, ReactNode>> = {
  blocked: <AlertTriangle className="size-4 text-orange-600" />,
  cancelled: <MinusCircle className="size-4 text-muted-foreground" />,
  completed: <CheckCircle2 className="size-4 text-green-600" />,
  failed: <XCircle className="size-4 text-red-600" />,
  "in-progress": <Loader2 className="size-4 animate-spin text-blue-600" />,
  partial: <AlertTriangle className="size-4 text-amber-600" />,
  running: <Loader2 className="size-4 animate-spin text-blue-600" />,
};

function StepStatusIcon({ status }: { status: AgentPlanStatus }) {
  return stepStatusIconByStatus[status] ?? <Circle className="size-4 text-muted-foreground" />;
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

export function ExplorationTaskInfoPanel({ monitor, loading }: { monitor: ExplorationMonitorState; loading: boolean }) {
  const { plan, steps, events } = monitor;
  const hasSteps = steps.length > 0;
  const [isPlanOpen, setIsPlanOpen] = useState(false);
  const isRunning =
    loading || monitor.phase === "executing" || monitor.phase === "planning" || monitor.phase === "planned";

  return (
    <div className="grid min-h-[620px] gap-5 lg:grid-cols-[380px_minmax(0,1fr)]">
      <aside className="flex h-[calc(100vh-210px)] min-h-[620px] flex-col overflow-hidden rounded-xl border border-border/70 bg-card text-card-foreground shadow-black/5 shadow-sm dark:shadow-black/20">
        <div className="flex min-h-12 items-center gap-3 border-b bg-muted/30 px-6 py-3">
          <div className="font-medium text-muted-foreground text-sm">执行步骤</div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {plan ? (
            <div className="mb-5 space-y-3">
              <button
                aria-expanded={isPlanOpen}
                className="flex w-full items-center gap-2 text-left"
                onClick={() => setIsPlanOpen((value) => !value)}
                type="button"
              >
                {isPlanOpen ? (
                  <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                )}
                <ListChecks className="size-4 text-primary" />
                <h3 className="font-semibold text-sm">探索计划</h3>
                {plan.total_steps > 0 ? (
                  <span className="ml-auto text-muted-foreground text-xs">{plan.total_steps} 个步骤</span>
                ) : null}
              </button>
              {isPlanOpen ? (
                <div className="space-y-3 rounded-xl border border-primary/15 bg-primary/5 p-4 text-sm leading-6">
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
                </div>
              ) : null}
            </div>
          ) : null}
          {loading && !hasSteps ? (
            <div className="flex items-start gap-3 text-muted-foreground text-sm">
              <Loader2 className="mt-0.5 size-4 animate-spin" />
              <span>加载中...</span>
            </div>
          ) : !hasSteps ? (
            <div className="text-muted-foreground text-sm">暂无步骤信息</div>
          ) : (
            <div className="space-y-2 pr-1">
              {steps.map((step) => (
                <ExplorationStepCard key={step.step_id} step={step} />
              ))}
            </div>
          )}
        </div>
      </aside>
      <main className="min-w-0">
        <div className="flex h-[calc(100vh-210px)] min-h-[620px] flex-col overflow-hidden rounded-xl border border-border/70 bg-card text-card-foreground shadow-black/5 shadow-sm dark:shadow-black/20">
          <div className="flex min-h-12 items-center gap-3 border-b bg-muted/30 px-6 py-3">
            <div className="font-medium text-muted-foreground text-sm">探索输出</div>
            {isRunning ? (
              <div className="ml-auto flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin" />
                执行中
              </div>
            ) : null}
          </div>
          <ExplorationExecutionTranscript events={events} loading={loading} />
        </div>
      </main>
    </div>
  );
}

function ExplorationStepCard({ step }: { step: ExplorationMonitorStep }) {
  const isExpanded = step.status === "running" || step.status === "in-progress" || step.status === "failed";
  return (
    <div className="rounded-xl border bg-background p-3 transition-colors hover:bg-muted/30">
      <div className="flex items-start gap-2">
        <div className="mt-0.5 shrink-0">
          <StepStatusIcon status={step.status} />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-medium font-mono text-sm">#{step.step_number}</span>
            <span className="truncate text-sm">{step.description}</span>
          </div>
          {step.module_name ? <div className="text-muted-foreground text-xs">模块: {step.module_name}</div> : null}
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

function ExplorationExecutionTranscript({ events, loading }: { events: ExplorationMonitorEvent[]; loading: boolean }) {
  const blocks = useMemo(() => buildExecutionTranscriptBlocks(events), [events]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);
  const [openToolIds, setOpenToolIds] = useState<Set<string>>(
    () => new Set(blocks.filter((block) => block.defaultOpen).map((block) => block.id)),
  );
  const blockVersion = blocks.map((block) => `${block.id}:${block.status}:${block.output.length}`).join("|");

  useEffect(() => {
    setOpenToolIds((current) => {
      const next = new Set(current);
      for (const block of blocks) {
        if (block.defaultOpen) {
          next.add(block.id);
        }
      }
      return next;
    });
  }, [blocks]);

  useEffect(() => {
    if (!stickToBottom) {
      return;
    }
    if (!blockVersion) {
      return;
    }
    const node = scrollRef.current;
    if (!node) {
      return;
    }
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [blockVersion, stickToBottom]);

  function handleScroll() {
    const node = scrollRef.current;
    if (!node) {
      return;
    }
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    setStickToBottom(distanceFromBottom < 48);
  }

  if (loading && blocks.length === 0) {
    return (
      <div className="flex flex-1 items-start gap-3 px-6 pt-8 text-muted-foreground text-sm">
        <Loader2 className="mt-0.5 size-4 animate-spin" />
        <span>等待探索输出...</span>
      </div>
    );
  }

  if (blocks.length === 0) {
    return <div className="flex-1 px-6 pt-8 text-muted-foreground text-sm">暂无探索输出</div>;
  }

  return (
    <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5 text-sm" onScroll={handleScroll} ref={scrollRef}>
      {blocks.map((block) =>
        block.type === "tool" ? (
          <ToolTranscriptItem
            block={block}
            isOpen={openToolIds.has(block.id)}
            key={block.id}
            onToggle={() =>
              setOpenToolIds((current) => {
                const next = new Set(current);
                if (next.has(block.id)) {
                  next.delete(block.id);
                } else {
                  next.add(block.id);
                }
                return next;
              })
            }
          />
        ) : (
          <DialogueTranscriptItem block={block} key={block.id} />
        ),
      )}
    </div>
  );
}

function buildExecutionTranscriptBlocks(events: ExplorationMonitorEvent[]): ExecutionTranscriptBlock[] {
  const blocks: ExecutionTranscriptBlock[] = [];
  const toolBlocks = new Map<string, ExecutionTranscriptBlock>();

  for (const event of [...events].reverse()) {
    const display = event.display;
    if (!display) {
      continue;
    }
    if (display.kind === "agent_run" && display.title === "开始页面探索") {
      continue;
    }
    const fields = display.fields?.filter((field) => field.label !== "结果") ?? [];
    const isToolEvent =
      event.type === "agent_tool_started" ||
      event.type === "agent_tool_completed" ||
      event.type === "agent_tool_failed";
    if (isToolEvent) {
      const blockKey = stringValue(event.payload?.step_id) || event.id;
      const existing = toolBlocks.get(blockKey);
      if (existing) {
        existing.title = display.title || existing.title;
        existing.output = display.summary || event.summary || existing.output;
        existing.fields = fields;
        existing.chips = display.chips ?? [];
        existing.status = event.status;
        existing.completedAt = event.occurred_at;
        existing.defaultOpen = false;
        continue;
      }
      const block: ExecutionTranscriptBlock = {
        id: blockKey,
        type: "tool",
        title: display.title || event.label,
        output: display.summary || event.summary,
        fields,
        chips: display.chips ?? [],
        status: event.status,
        occurredAt: event.occurred_at,
        completedAt: "",
        toolName: stringValue(event.payload?.tool_name),
        defaultOpen: false,
      };
      toolBlocks.set(blockKey, block);
      blocks.push(block);
      continue;
    }
    blocks.push({
      id: event.id,
      type: "message",
      title: display.title || event.label,
      output: display.summary || event.summary,
      fields,
      chips: display.chips ?? [],
      status: event.status,
      occurredAt: event.occurred_at,
      completedAt: "",
      toolName: "",
      defaultOpen: false,
    });
  }

  return blocks;
}

function DialogueTranscriptItem({ block }: { block: ExecutionTranscriptBlock }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <span>{block.title}</span>
        {block.occurredAt ? <span className="ml-auto text-xs">{formatTime(block.occurredAt)}</span> : null}
      </div>
      {block.output ? (
        <div className="max-w-4xl whitespace-pre-wrap break-words text-sm leading-6">{block.output}</div>
      ) : null}
      <ExecutionTranscriptStatus status={block.status} />
    </div>
  );
}

function ToolTranscriptItem({
  block,
  isOpen,
  onToggle,
}: {
  block: ExecutionTranscriptBlock;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="space-y-2">
      <button
        aria-expanded={isOpen}
        className="flex w-full items-center gap-2 text-left text-muted-foreground text-sm"
        onClick={onToggle}
        type="button"
      >
        {isOpen ? <ChevronDown className="size-4 shrink-0" /> : <ChevronRight className="size-4 shrink-0" />}
        <span className="truncate">{block.title}</span>
        {block.occurredAt ? <span className="ml-auto text-xs">{formatTime(block.occurredAt)}</span> : null}
      </button>
      {isOpen ? (
        <div className="ml-6 max-w-4xl rounded-xl border bg-background px-5 py-4 shadow-sm">
          <div className="mb-3 font-medium text-foreground/80 text-sm">Output</div>
          {block.output ? (
            <div className="whitespace-pre-wrap break-words text-sm leading-6">{block.output}</div>
          ) : null}
          <ExecutionOutputDetails block={block} />
        </div>
      ) : null}
      <div className={isOpen ? "ml-6" : "ml-6"}>
        <ExecutionTranscriptStatus status={block.status} />
      </div>
    </div>
  );
}

function ExecutionOutputDetails({ block }: { block: ExecutionTranscriptBlock }) {
  const hasDetails = block.fields.length > 0 || block.chips.length > 0;
  if (!hasDetails) {
    return null;
  }
  return (
    <div className="mt-4 space-y-2 border-t pt-4 text-muted-foreground text-xs leading-6">
      {block.toolName ? (
        <div>
          <span>工具: </span>
          <span className="font-mono">{block.toolName}</span>
        </div>
      ) : null}
      {block.fields.map((field) => (
        <div className={field.tone ? getFieldToneClass(field.tone) : undefined} key={`${field.label}:${field.value}`}>
          <span>{field.label}: </span>
          <span className={field.mono ? "font-mono" : ""}>{field.value}</span>
        </div>
      ))}
      {block.chips.length > 0 ? (
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {block.chips.map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ExecutionTranscriptStatus({ status }: { status: AgentPlanStatus }) {
  if (status === "completed") {
    return (
      <div className="flex items-center gap-2 text-foreground text-sm">
        <CheckCircle2 className="size-4 text-muted-foreground" />
        <span>Done</span>
      </div>
    );
  }
  if (status === "running" || status === "in-progress") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="size-4 animate-spin" />
        <span>执行中</span>
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="flex items-center gap-2 text-red-600 text-sm">
        <XCircle className="size-4" />
        <span>失败</span>
      </div>
    );
  }
  if (status === "cancelled") {
    return (
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <MinusCircle className="size-4" />
        <span>已取消</span>
      </div>
    );
  }
  return null;
}

function stringValue(value: unknown): string {
  return value ? String(value) : "";
}

function getFieldToneClass(tone: ReadableExecutionField["tone"]): string {
  switch (tone) {
    case "success":
      return "text-green-600";
    case "warning":
      return "text-amber-600";
    case "danger":
      return "text-red-600";
    default:
      return "text-muted-foreground";
  }
}
