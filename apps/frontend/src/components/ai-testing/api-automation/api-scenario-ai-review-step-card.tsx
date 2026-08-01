"use client";

import { ArrowDown, ArrowUp, CheckCheck, Link2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ApiScenarioAiPlanValueSource, ApiScenarioAiReviewStep } from "@/lib/api-client";
import { cn } from "@/lib/utils";

import { ApiScenarioAiReviewFieldRow } from "./api-scenario-ai-review-field";

const methodTone: Record<string, string> = {
  GET: "border-emerald-300 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200",
  POST: "border-sky-300 bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-200",
  PUT: "border-amber-300 bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-200",
  PATCH: "border-orange-300 bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-200",
  DELETE: "border-rose-300 bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200",
};

export function ApiScenarioAiReviewStepCard({
  step,
  canMoveUp,
  canMoveDown,
  onMove,
  onChangeField,
  onConfirmField,
  onConfirmStep,
}: {
  step: ApiScenarioAiReviewStep;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMove: (direction: -1 | 1) => void;
  onChangeField: (fieldId: string, source: ApiScenarioAiPlanValueSource) => void;
  onConfirmField: (fieldId: string) => void;
  onConfirmStep: () => void;
}) {
  const pendingGroups = step.field_groups
    .map((group) => ({ ...group, fields: group.fields.filter((field) => field.status === "pending") }))
    .filter((group) => group.fields.length > 0);
  const resolvedGroups = step.field_groups
    .map((group) => ({ ...group, fields: group.fields.filter((field) => field.status !== "pending") }))
    .filter((group) => group.fields.length > 0);
  const resolvedCount = resolvedGroups.reduce((total, group) => total + group.fields.length, 0);

  return (
    <article className="overflow-hidden rounded-xl border bg-card shadow-xs" data-step-id={step.step_id}>
      <header className="flex flex-wrap items-start gap-3 border-b bg-muted/20 px-4 py-3.5">
        <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
          {step.order}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-sm">步骤 {step.order}</span>
            <Badge className={cn("font-mono text-[10px]", methodTone[step.method])} variant="outline">
              {step.method}
            </Badge>
            {step.review_summary.pending_count > 0 ? (
              <Badge variant="outline">{step.review_summary.pending_count} 项待确认</Badge>
            ) : (
              <Badge className="text-emerald-700 dark:text-emerald-300" variant="secondary">
                已确认
              </Badge>
            )}
          </div>
          <div className="mt-1 truncate font-mono text-muted-foreground text-xs">{step.path}</div>
          {step.depends_on.length > 0 ? (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Link2 className="size-3" /> 依赖 {step.depends_on.join("、")}
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          <Button disabled={!canMoveUp} onClick={() => onMove(-1)} size="icon" variant="ghost">
            <ArrowUp />
          </Button>
          <Button disabled={!canMoveDown} onClick={() => onMove(1)} size="icon" variant="ghost">
            <ArrowDown />
          </Button>
          {step.review_summary.pending_count > 0 ? (
            <Button className="h-8" onClick={onConfirmStep} size="sm" variant="outline">
              <CheckCheck /> 确认本步骤
            </Button>
          ) : null}
        </div>
      </header>

      {pendingGroups.map((group) => (
        <section key={group.location}>
          <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
            <h4 className="font-semibold text-xs">{group.label}</h4>
            <span className="text-[11px] text-muted-foreground">{group.fields.length} 项待确认</span>
          </div>
          <div className="hidden grid-cols-[minmax(130px,1fr)_minmax(150px,1fr)_minmax(260px,1.6fr)_110px] gap-3 border-b bg-muted/10 px-3 py-2 text-[10px] text-muted-foreground md:grid">
            <span>字段</span>
            <span>AI 建议</span>
            <span>最终值</span>
            <span className="text-right">状态</span>
          </div>
          {group.fields.map((field) => (
            <ApiScenarioAiReviewFieldRow
              field={field}
              key={field.field_id}
              onChange={(source) => onChangeField(field.field_id, source)}
              onConfirm={() => onConfirmField(field.field_id)}
            />
          ))}
        </section>
      ))}

      {resolvedCount > 0 ? (
        <details className="border-t" open={pendingGroups.length === 0}>
          <summary className="cursor-pointer px-4 py-3 font-medium text-xs">已自动确定 {resolvedCount} 项</summary>
          {resolvedGroups.map((group) => (
            <section className="border-t" key={group.location}>
              <div className="bg-muted/10 px-4 py-2 font-medium text-xs">{group.label}</div>
              {group.fields.map((field) => (
                <ApiScenarioAiReviewFieldRow
                  field={field}
                  key={field.field_id}
                  onChange={(source) => onChangeField(field.field_id, source)}
                  onConfirm={() => onConfirmField(field.field_id)}
                />
              ))}
            </section>
          ))}
        </details>
      ) : null}
    </article>
  );
}
