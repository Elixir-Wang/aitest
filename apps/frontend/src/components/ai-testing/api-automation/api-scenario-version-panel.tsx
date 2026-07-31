import { useState } from "react";

import { Check, ChevronDown, Clock3, GitCommitHorizontal, History, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiAutomationScenarioRevision } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ApiScenarioVersionPanelProps = {
  busy: boolean;
  currentRevision: number;
  revisions: ApiAutomationScenarioRevision[];
  onRestore: (revision: number) => void;
};

export function ApiScenarioVersionPanel({ busy, currentRevision, revisions, onRestore }: ApiScenarioVersionPanelProps) {
  const [expandedRevision, setExpandedRevision] = useState<number | null>(currentRevision || null);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--primary),transparent_92%),transparent_36%)] p-6">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-primary">
              <History className="size-4" />
              <span className="font-medium text-xs uppercase tracking-[0.18em]">Revision Timeline</span>
            </div>
            <h2 className="mt-2 font-semibold text-xl">版本记录</h2>
            <p className="mt-1 max-w-2xl text-muted-foreground text-sm">
              每次保存都会生成可运行版本，最多保留最近 5 个。可展开查看完整编排，恢复历史版本会生成新版本。
            </p>
          </div>
          <Badge className="border-primary/20 bg-primary/8 text-primary" variant="outline">
            {revisions.length} 个快照
          </Badge>
        </div>

        {revisions.length === 0 ? (
          <div className="mt-8 grid min-h-64 place-items-center rounded-2xl border border-dashed bg-card/70 text-center">
            <div>
              <Clock3 className="mx-auto size-9 text-muted-foreground/50" />
              <div className="mt-3 font-medium">尚无版本</div>
              <p className="mt-1 text-muted-foreground text-sm">完成场景配置并保存后，版本会显示在这里。</p>
            </div>
          </div>
        ) : (
          <div className="relative mt-8 space-y-4 before:absolute before:top-8 before:bottom-8 before:left-[25px] before:w-px before:bg-border">
            {revisions.map((revision) => {
              const current = revision.revision === currentRevision;
              const expanded = revision.revision === expandedRevision;
              return (
                <article
                  className={cn(
                    "relative ml-12 rounded-2xl border bg-card/90 p-5 shadow-sm transition-shadow hover:shadow-md",
                    current &&
                      "border-primary/35 shadow-[0_12px_32px_color-mix(in_srgb,var(--primary),transparent_90%)]",
                  )}
                  key={revision.revision}
                >
                  <div
                    className={cn(
                      "absolute top-6 -left-[35px] grid size-7 place-items-center rounded-full border-4 border-background bg-muted text-muted-foreground",
                      current && "bg-primary text-primary-foreground",
                    )}
                  >
                    {current ? <Check className="size-3.5" /> : <GitCommitHorizontal className="size-3.5" />}
                  </div>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-base">版本 v{revision.revision}</span>
                        {current ? <Badge className="bg-emerald-50 text-emerald-700">当前版本</Badge> : null}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground text-xs">
                        <span>{formatRevisionTime(revision.created_at)}</span>
                        <span>保存人 {revision.created_by}</span>
                        <span>{revision.step_count} 个步骤</span>
                      </div>
                      <div className="mt-3 inline-flex rounded-md bg-muted px-2 py-1 font-mono text-[10px] text-muted-foreground">
                        {revision.published_hash.slice(0, 12)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        aria-expanded={expanded}
                        onClick={() => setExpandedRevision(expanded ? null : revision.revision)}
                        size="sm"
                        variant="outline"
                      >
                        <ChevronDown className={cn("transition-transform", expanded && "rotate-180")} />
                        查看编排
                      </Button>
                      {!current ? (
                        <Button
                          disabled={busy}
                          onClick={() => onRestore(revision.revision)}
                          size="sm"
                          variant="outline"
                        >
                          <RotateCcw />
                          恢复此版本
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  {expanded ? (
                    <div className="mt-5 border-t pt-4">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <span className="font-medium text-sm">{revision.snapshot.name}</span>
                        <span className="text-muted-foreground text-xs">
                          {revision.snapshot.steps.length} 个执行步骤
                        </span>
                      </div>
                      <div className="divide-y overflow-hidden rounded-md border">
                        {revision.snapshot.steps.map((step, index) => (
                          <div
                            className="flex items-center gap-3 bg-background px-3 py-2.5"
                            key={`${revision.revision}-${step.id}`}
                          >
                            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-muted font-medium text-[11px]">
                              {index + 1}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="truncate font-medium text-sm">{step.name || step.id}</div>
                              <div className="mt-0.5 truncate text-muted-foreground text-xs">
                                {step.endpoint
                                  ? `${step.endpoint.method} ${step.endpoint.path}`
                                  : step.step_type.replaceAll("_", " ")}
                              </div>
                            </div>
                            <Badge variant="secondary">{step.enabled ? "启用" : "停用"}</Badge>
                          </div>
                        ))}
                        {revision.snapshot.steps.length === 0 ? (
                          <div className="px-3 py-8 text-center text-muted-foreground text-sm">该版本没有执行步骤</div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function formatRevisionTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}
