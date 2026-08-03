"use client";

import { CheckCheck, GitBranch, Loader2, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import type { ApiScenarioAiPlanValueSource, ApiScenarioAiReviewPlan } from "@/lib/api-client";

import type { ApiScenarioAiReviewSourceOptions } from "./api-scenario-ai-review-field";
import { ApiScenarioAiReviewStepCard } from "./api-scenario-ai-review-step-card";

function referencedSourceNames(plan: ApiScenarioAiReviewPlan, type: "secret" | "user_input") {
  return Array.from(
    new Set(
      plan.steps.flatMap((step) =>
        step.field_groups.flatMap((group) =>
          group.fields.flatMap((field) => {
            const source = field.resolved ?? field.proposal;
            if (source.type !== type) return [];
            return [type === "secret" ? (source.key ?? "") : (source.name ?? "")];
          }),
        ),
      ),
    ),
  ).filter(Boolean);
}

export function ApiScenarioAiReviewDrawer({
  busy,
  open,
  plan,
  onOpenChange,
  onApply,
  onDiscard,
  onConfirmAll,
  onConfirmStep,
  onConfirmField,
  onChangeField,
  onMoveStep,
  environmentVariableNames,
  scenarioVariableNames,
}: {
  busy: boolean;
  open: boolean;
  plan: ApiScenarioAiReviewPlan;
  onOpenChange: (open: boolean) => void;
  onApply: () => void;
  onDiscard: () => void;
  onConfirmAll: () => void;
  onConfirmStep: (stepId: string) => void;
  onConfirmField: (stepId: string, fieldId: string) => void;
  onChangeField: (stepId: string, fieldId: string, source: ApiScenarioAiPlanValueSource) => void;
  onMoveStep: (stepId: string, direction: -1 | 1) => void;
  environmentVariableNames: string[];
  scenarioVariableNames: string[];
}) {
  const pendingCount = plan.steps.reduce((total, step) => total + step.review_summary.pending_count, 0);
  const canApply = plan.review_status === "ready" && plan.validation.valid;
  const secretKeys = referencedSourceNames(plan, "secret");
  const userInputs = referencedSourceNames(plan, "user_input");

  return (
    <Drawer direction="right" handleOnly open={open} onOpenChange={onOpenChange}>
      <DrawerContent className="grid h-full w-full grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden bg-background p-0 data-[vaul-drawer-direction=right]:w-[min(96vw,980px)] data-[vaul-drawer-direction=right]:sm:max-w-[980px]">
        <DrawerHeader className="relative border-b bg-muted/20 px-5 py-4 sm:px-6">
          <div className="flex flex-wrap items-center gap-3">
            <div className="grid size-9 place-items-center rounded-lg bg-primary text-primary-foreground">
              <GitBranch className="size-4" />
            </div>
            <div className="min-w-0 flex-1">
              <DrawerTitle className="text-base sm:text-lg">审核 AI 编排方案</DrawerTitle>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-muted-foreground text-xs">
                <span>{plan.scenario_name}</span>
                <span>·</span>
                <span>{plan.steps.length} 个接口步骤</span>
                <Badge variant={pendingCount > 0 ? "outline" : "secondary"}>
                  {pendingCount > 0 ? `${pendingCount} 项待确认` : "审核完成"}
                </Badge>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              {pendingCount > 0 ? (
                <Button disabled={busy} onClick={onConfirmAll} size="sm" variant="outline">
                  <CheckCheck /> 全部采用 AI 建议
                </Button>
              ) : null}
              <Button disabled={busy} onClick={onDiscard} size="sm" variant="outline">
                <Trash2 />
                放弃方案
              </Button>
              <Button disabled={busy || !canApply} onClick={onApply} size="sm">
                {busy ? <Loader2 className="animate-spin" /> : <CheckCheck />}
                应用为新版本
              </Button>
            </div>
          </div>
          <div className="absolute inset-y-0 left-0 z-10 flex w-3 items-center justify-center">
            <DrawerHandle
              aria-label="拖动关闭抽屉"
              className="h-12! w-1.5! cursor-ew-resize touch-none rounded-full bg-border!"
            />
          </div>
        </DrawerHeader>

        <div className="select-text! min-h-0 space-y-4 overflow-y-auto bg-muted/10 px-4 py-4 sm:px-6">
          {plan.validation.errors.length > 0 ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-destructive text-xs">
              {plan.validation.errors.join("；")}
            </div>
          ) : null}
          {plan.steps.map((step, index) => (
            <ApiScenarioAiReviewStepCard
              canMoveDown={index < plan.steps.length - 1}
              canMoveUp={index > 0}
              key={step.step_id}
              onChangeField={(fieldId, source) => onChangeField(step.step_id, fieldId, source)}
              onConfirmField={(fieldId) => onConfirmField(step.step_id, fieldId)}
              onConfirmStep={() => onConfirmStep(step.step_id)}
              onMove={(direction) => onMoveStep(step.step_id, direction)}
              sourceOptions={
                {
                  environmentVariables: environmentVariableNames,
                  scenarioVariables: scenarioVariableNames,
                  secretKeys,
                  userInputs,
                  stepOutputs: plan.steps
                    .filter((candidate) => candidate.order < step.order)
                    .flatMap((candidate) =>
                      candidate.extractors.map((extractor) => ({
                        stepId: candidate.step_id,
                        stepName: candidate.name || `步骤 ${candidate.order}`,
                        variable: extractor.name,
                      })),
                    ),
                } satisfies ApiScenarioAiReviewSourceOptions
              }
              step={step}
            />
          ))}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
