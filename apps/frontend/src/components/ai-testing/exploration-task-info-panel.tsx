import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  AlertTriangle,
  Bot,
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
import type {
  ExplorationMonitorEvent,
  ExplorationMonitorState,
  ExplorationMonitorStep,
  ReadableExecutionField,
} from "@/lib/exploration-types";

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

export function ExplorationTaskInfoPanel({
  monitor,
  loading,
  status,
}: {
  monitor: ExplorationMonitorState;
  loading: boolean;
  status: AgentPlanStatus;
}) {
  const { plan, steps, events } = monitor;
  const hasSteps = steps.length > 0;
  const [isPlanOpen, setIsPlanOpen] = useState(false);
  const isRunning =
    loading || monitor.phase === "executing" || monitor.phase === "planning" || monitor.phase === "planned";

  return (
    <div className="grid min-h-[620px] gap-4 lg:grid-cols-[380px_minmax(0,1fr)]">
      <aside className="flex h-[calc(100vh-210px)] min-h-[620px] flex-col overflow-hidden rounded-lg border border-border/70 bg-card text-card-foreground shadow-[0_8px_30px_rgb(31_42_55_/_0.05)] dark:shadow-black/20">
        <div className="flex min-h-14 items-center gap-3 border-border/70 border-b px-5 py-3">
          <ListChecks className="size-4 text-primary" />
          <div className="font-semibold text-sm">执行步骤</div>
          {steps.length > 0 ? <span className="ml-auto text-muted-foreground text-xs">{steps.length} 个步骤</span> : null}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
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
            <div className="space-y-3 pr-1">
              {steps.map((step, index) => (
                <ExplorationStepCard isLast={index === steps.length - 1} key={step.step_id} step={step} />
              ))}
            </div>
          )}
        </div>
      </aside>
      <main className="min-w-0">
        <div className="flex h-[calc(100vh-210px)] min-h-[620px] flex-col overflow-hidden rounded-lg border border-border/70 bg-card text-card-foreground shadow-[0_8px_30px_rgb(31_42_55_/_0.05)] dark:shadow-black/20">
          <div className="flex min-h-14 items-center gap-3 border-border/70 border-b px-5 py-3">
            <Bot className="size-4 text-primary" />
            <div className="font-semibold text-sm">探索输出</div>
            <RunStatusBadge className="ml-auto" isLoading={loading || isRunning} status={status} />
          </div>
          <ExplorationExecutionTranscript autoScrollEnabled={isRunning} events={events} loading={loading} />
        </div>
      </main>
    </div>
  );
}

function RunStatusBadge({
  className = "",
  isLoading,
  status,
}: {
  className?: string;
  isLoading: boolean;
  status: AgentPlanStatus;
}) {
  const displayStatus = isLoading && status === "pending" ? "running" : status;
  const content = runStatusContent(displayStatus);
  return (
    <div
      className={`${className} flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs ${content.className}`}
    >
      {content.icon}
      <span>{content.label}</span>
    </div>
  );
}

function runStatusContent(status: AgentPlanStatus): { className: string; icon: ReactNode; label: string } {
  if (status === "completed") {
    return {
      className:
        "border-green-200 bg-green-50 text-green-700 dark:border-green-500/30 dark:bg-green-500/10 dark:text-green-300",
      icon: <CheckCircle2 className="size-3.5" />,
      label: "已完成",
    };
  }
  if (status === "failed" || status === "blocked") {
    return {
      className: "border-red-200 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300",
      icon: <XCircle className="size-3.5" />,
      label: "失败",
    };
  }
  if (status === "cancelled") {
    return {
      className: "border-muted bg-muted/40 text-muted-foreground",
      icon: <MinusCircle className="size-3.5" />,
      label: "已停止",
    };
  }
  if (status === "running" || status === "in-progress" || status === "stopping") {
    return {
      className:
        "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-500/30 dark:bg-blue-500/10 dark:text-blue-300",
      icon: <Loader2 className="size-3.5 animate-spin" />,
      label: status === "stopping" ? "停止中" : "执行中",
    };
  }
  return {
    className: "border-muted bg-muted/30 text-muted-foreground",
    icon: <Circle className="size-3.5" />,
    label: "待开始",
  };
}

function ExplorationStepCard({ isLast, step }: { isLast: boolean; step: ExplorationMonitorStep }) {
  const isExpanded = step.status === "running" || step.status === "in-progress" || step.status === "failed";
  const isActive = step.status === "running" || step.status === "in-progress";
  const surfaceClass =
    step.status === "failed"
      ? "border-red-200 bg-red-50/70 dark:border-red-500/30 dark:bg-red-500/10"
      : isActive
        ? "border-primary/30 bg-primary/5 shadow-sm"
        : step.status === "completed"
          ? "border-border/70 bg-card"
          : "border-border/60 bg-muted/15";
  const railClass =
    step.status === "completed"
      ? "border-green-300 dark:border-green-500/50"
      : step.status === "failed"
        ? "border-red-200 dark:border-red-500/40"
        : "border-border border-dashed";

  return (
    <div className="relative pl-8">
      {!isLast ? (
        <span
          aria-hidden="true"
          className={`absolute top-6 bottom-[-0.75rem] left-[9px] border-l ${railClass}`}
        />
      ) : null}
      <span className="absolute top-4 left-0 z-10 flex size-5 items-center justify-center rounded-full bg-card ring-4 ring-card">
        <StepStatusIcon status={step.status} />
      </span>
      <div className={`rounded-lg border px-3 py-3 transition-colors hover:border-primary/25 ${surfaceClass}`}>
        <div className="min-w-0 space-y-1">
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

function ExplorationExecutionTranscript({
  autoScrollEnabled,
  events,
  loading,
}: {
  autoScrollEnabled: boolean;
  events: ExplorationMonitorEvent[];
  loading: boolean;
}) {
  const blocks = useMemo(() => buildExecutionTranscriptBlocks(events), [events]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(autoScrollEnabled);
  const [openToolIds, setOpenToolIds] = useState<Set<string>>(
    () => new Set(blocks.filter((block) => block.defaultOpen).map((block) => block.id)),
  );
  const blockVersion = useMemo(
    () => blocks.map((block) => `${block.id}:${block.status}:${block.output.length}`).join("|"),
    [blocks],
  );
  const lastBlockSignatureRef = useRef<string>("");
  const previousAutoScrollEnabledRef = useRef(autoScrollEnabled);

  useEffect(() => {
    if (!previousAutoScrollEnabledRef.current && autoScrollEnabled) {
      setStickToBottom(true);
    }
    previousAutoScrollEnabledRef.current = autoScrollEnabled;
  }, [autoScrollEnabled]);

  useEffect(() => {
    if (blockVersion === lastBlockSignatureRef.current) {
      return;
    }
    lastBlockSignatureRef.current = blockVersion;
    if (!autoScrollEnabled || !stickToBottom) {
      return;
    }
    const node = scrollRef.current;
    if (!node) {
      return;
    }
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [autoScrollEnabled, blockVersion, stickToBottom]);

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
    <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-6 text-sm" onScroll={handleScroll} ref={scrollRef}>
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
    if (event.type === "agent_step_started" && display.kind === "agent_run") {
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
    <div className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
      <div className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary ring-4 ring-primary/5">
        <Bot className="size-4" />
      </div>
      <div className="min-w-0 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-semibold text-primary">{block.title}</span>
          {block.occurredAt ? <span className="ml-auto text-muted-foreground text-xs">{formatTime(block.occurredAt)}</span> : null}
        </div>
        {block.output ? (
          <div className="max-w-4xl whitespace-pre-wrap break-words text-sm leading-6">{block.output}</div>
        ) : null}
        <ExecutionTranscriptStatus status={block.status} />
      </div>
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
    <div className="relative ml-3 space-y-2 border-primary/25 border-l border-dashed pl-8">
      <span aria-hidden="true" className="absolute top-1.5 -left-[5px] size-2.5 rounded-full border-2 border-card bg-primary/70" />
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
        <div className="max-w-4xl rounded-lg border border-border/70 bg-muted/15 px-5 py-4">
          <div className="mb-3 font-medium text-foreground/80 text-sm">Output</div>
          {block.output ? (
            <div className="whitespace-pre-wrap break-words text-sm leading-6">{block.output}</div>
          ) : null}
          <ExecutionOutputDetails block={block} />
        </div>
      ) : null}
      <div>
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
