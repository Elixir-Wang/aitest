import { Check, Clock3, GitCommitHorizontal, History, RotateCcw } from "lucide-react";

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
  return (
    <div className="min-h-[620px] bg-[radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--primary),transparent_92%),transparent_36%)] p-6">
      <div className="mx-auto max-w-4xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-primary">
              <History className="size-4" />
              <span className="font-medium text-xs uppercase tracking-[0.18em]">Revision Timeline</span>
            </div>
            <h2 className="mt-2 font-semibold text-xl">版本记录</h2>
            <p className="mt-1 max-w-2xl text-muted-foreground text-sm">
              每次发布都会冻结接口资产与步骤配置。恢复历史版本只生成草稿，不会覆盖当前已发布版本。
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
              <div className="mt-3 font-medium">尚未发布版本</div>
              <p className="mt-1 text-muted-foreground text-sm">完成场景配置并发布后，版本快照会显示在这里。</p>
            </div>
          </div>
        ) : (
          <div className="relative mt-8 space-y-4 before:absolute before:top-8 before:bottom-8 before:left-[25px] before:w-px before:bg-border">
            {revisions.map((revision) => {
              const current = revision.revision === currentRevision;
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
                        <span>发布人 {revision.created_by}</span>
                        <span>{revision.step_count} 个步骤</span>
                      </div>
                      <div className="mt-3 inline-flex rounded-md bg-muted px-2 py-1 font-mono text-[10px] text-muted-foreground">
                        {revision.published_hash.slice(0, 12)}
                      </div>
                    </div>
                    {!current ? (
                      <Button disabled={busy} onClick={() => onRestore(revision.revision)} size="sm" variant="outline">
                        <RotateCcw />
                        恢复为草稿
                      </Button>
                    ) : null}
                  </div>
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
