import { Check, Circle, LoaderCircle, XCircle } from "lucide-react";

import type { PerformanceAnalysis } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const STEPS = [
  { key: "collecting", label: "收集运行证据" },
  { key: "analyzing", label: "对照接口定义并分析失败模式" },
  { key: "waiting_approval", label: "生成只读诊断建议" },
] as const;

export function PerformanceAiAnalysisProgress({ status }: { status: PerformanceAnalysis["status"] }) {
  const activeIndex = status === "collecting" ? 0 : status === "analyzing" ? 1 : 2;
  const failed = status === "failed";
  const finished = status === "waiting_approval" || status === "rejected";

  return (
    <div className="space-y-2 rounded-xl border bg-muted/25 p-3">
      {STEPS.map((step, index) => {
        const completed = finished || (!failed && index < activeIndex);
        const active = !finished && !failed && index === activeIndex;
        return (
          <div className="flex items-center gap-2 text-sm" key={step.key}>
            {failed && index === activeIndex ? (
              <XCircle className="size-4 text-destructive" />
            ) : completed ? (
              <Check className="size-4 text-emerald-600" />
            ) : active ? (
              <LoaderCircle className="size-4 animate-spin text-blue-600" />
            ) : (
              <Circle className={cn("size-4", active ? "text-blue-600" : "text-muted-foreground")} />
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
