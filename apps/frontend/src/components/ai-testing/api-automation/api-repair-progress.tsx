import { Check, Circle, CircleDot, LoaderCircle, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

const STEPS = [
  { key: "diagnosing", label: "分析失败原因" },
  { key: "waiting_approval", label: "确认代码修改" },
  { key: "candidate_generating", label: "生成候选修改" },
  { key: "candidate_validating", label: "验证候选修改" },
  { key: "applying", label: "应用正式代码" },
] as const;

const ACTIVE_INDEX: Record<string, number> = {
  queued: 0,
  collecting_context: 0,
  diagnosing: 0,
  proposal_ready: 1,
  waiting_approval: 1,
  candidate_generating: 2,
  candidate_validating: 3,
  ready_to_apply: 4,
  applying: 4,
  rerunning: 4,
  completed: 4,
  proposal_rejected: 1,
  rejected: 1,
  superseded: 1,
};

export function ApiRepairProgress({ status }: { status: string }) {
  const activeIndex = ACTIVE_INDEX[status] ?? 0;
  const failed = status === "failed";
  const finished = status === "completed";
  const diagnosisOnly = status === "proposal_ready";
  const waitingForUser = status === "waiting_approval" || status === "ready_to_apply";
  const visibleSteps = diagnosisOnly ? STEPS.slice(0, 1) : STEPS;

  return (
    <div className="space-y-2 rounded-lg border bg-muted/25 p-3">
      {visibleSteps.map((step, index) => {
        const completed = finished || diagnosisOnly || (!failed && index < activeIndex);
        const active = !finished && !failed && !diagnosisOnly && index === activeIndex;
        return (
          <div className="flex items-center gap-2 text-sm" key={step.key}>
            {failed && index === activeIndex ? (
              <XCircle className="size-4 text-destructive" />
            ) : completed ? (
              <Check className="size-4 text-emerald-600" />
            ) : active && waitingForUser ? (
              <CircleDot className="size-4 text-blue-600" />
            ) : active ? (
              <LoaderCircle className="size-4 animate-spin text-blue-600" />
            ) : (
              <Circle className="size-4 text-muted-foreground" />
            )}
            <span className={cn(active && "font-medium text-foreground", !active && "text-muted-foreground")}>
              {step.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function apiRepairStatusLabel(status: string) {
  return (
    (
      {
        queued: "等待执行",
        collecting_context: "分析失败原因",
        diagnosing: "分析失败原因",
        proposal_ready: "诊断完成，无需改代码",
        waiting_approval: "等待确认代码修改",
        candidate_generating: "生成候选修改",
        candidate_validating: "验证候选修改",
        ready_to_apply: "等待应用正式代码",
        applying: "正在应用正式代码",
        rerunning: "正在重新执行",
        completed: "代码修改完成",
        proposal_rejected: "代码修改已放弃",
        rejected: "代码修改已拒绝",
        superseded: "代码修改已更新",
        failed: "修复失败",
      } as Record<string, string>
    )[status] ?? status
  );
}
