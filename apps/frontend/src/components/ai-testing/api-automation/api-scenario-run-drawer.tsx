"use client";

import { useEffect, useState } from "react";

import { ArrowUpRight, CheckCircle2, CircleDashed, Clock3, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ApiAutomationScenarioRunResult, ApiAutomationScenarioStepResult } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ApiScenarioRunDrawerProps = {
  open: boolean;
  result: ApiAutomationScenarioRunResult | null;
  runId: string;
  status: string;
  onOpenChange: (open: boolean) => void;
  onJumpToStep: (stepId: string) => void;
};

export function ApiScenarioRunDrawer({
  open,
  result,
  runId,
  status,
  onOpenChange,
  onJumpToStep,
}: ApiScenarioRunDrawerProps) {
  const [selectedStepId, setSelectedStepId] = useState("");
  useEffect(() => setSelectedStepId(result?.steps[0]?.step_id ?? ""), [result]);
  const selectedStep = result?.steps.find((step) => step.step_id === selectedStepId) ?? result?.steps[0] ?? null;

  return (
    <Drawer onOpenChange={onOpenChange} open={open}>
      <DrawerContent className="max-h-[82vh]">
        <DrawerHeader className="border-b px-6 pb-4 text-left">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <DrawerTitle>场景运行诊断</DrawerTitle>
                <RunStatusBadge status={result?.status ?? status} />
              </div>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">{runId || "等待运行记录"}</p>
            </div>
            <div className="flex items-center gap-4 text-muted-foreground text-xs">
              <span>
                {result
                  ? `${result.steps.filter((step) => step.status === "passed").length}/${result.steps.length} 步通过`
                  : "正在采集步骤结果"}
              </span>
              <span>{result ? `${Math.round(result.duration_ms)} ms` : "—"}</span>
            </div>
          </div>
        </DrawerHeader>

        {!result ? (
          <div className="grid min-h-80 place-items-center bg-muted/10">
            <div className="text-center">
              <CircleDashed className="mx-auto size-8 animate-spin text-sky-600" />
              <div className="mt-3 font-medium">场景正在运行</div>
              <p className="mt-1 text-muted-foreground text-sm">完成后自动展示每个步骤的请求、响应和变量。</p>
            </div>
          </div>
        ) : (
          <div className="min-h-0 overflow-y-auto">
            <div className="border-b bg-[linear-gradient(90deg,#f8fafc,#eff6ff)] px-6 py-4">
              <div className="flex min-w-max items-center gap-2">
                {result.steps.map((step, index) => (
                  <div className="flex items-center" key={step.step_id}>
                    <button
                      className={cn(
                        "flex min-w-36 items-center gap-2 rounded-xl border bg-background px-3 py-2 text-left shadow-sm transition-all",
                        selectedStep?.step_id === step.step_id && "border-primary/50 ring-2 ring-primary/10",
                      )}
                      onClick={() => setSelectedStepId(step.step_id)}
                      type="button"
                    >
                      <StepStatusIcon status={step.status} />
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-xs">{step.name}</span>
                        <span className="text-[10px] text-muted-foreground">{Math.round(step.duration_ms)} ms</span>
                      </span>
                    </button>
                    {index < result.steps.length - 1 ? <span className="mx-1 h-px w-5 bg-border" /> : null}
                  </div>
                ))}
              </div>
            </div>

            {selectedStep ? (
              <div className="grid min-h-[390px] grid-cols-[260px_minmax(0,1fr)]">
                <aside className="border-r bg-muted/15 p-3">
                  <div className="px-2 pb-2 font-medium text-muted-foreground text-xs">执行步骤</div>
                  <div className="space-y-1">
                    {result.steps.map((step, index) => (
                      <button
                        className={cn(
                          "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left",
                          selectedStep.step_id === step.step_id ? "bg-background shadow-sm" : "hover:bg-background/70",
                        )}
                        key={step.step_id}
                        onClick={() => setSelectedStepId(step.step_id)}
                        type="button"
                      >
                        <span className="grid size-6 place-items-center rounded-md bg-muted text-[10px]">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-xs">{step.name}</span>
                          <span className="text-[10px] text-muted-foreground">{stepStatusLabel(step.status)}</span>
                        </span>
                        <StepStatusIcon status={step.status} />
                      </button>
                    ))}
                  </div>
                </aside>

                <main className="min-w-0 p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{selectedStep.name}</h3>
                        <Badge variant="outline">{selectedStep.step_type}</Badge>
                      </div>
                      <p className="mt-1 text-muted-foreground text-xs">
                        耗时 {Math.round(selectedStep.duration_ms)} ms
                      </p>
                    </div>
                    <Button
                      onClick={() => {
                        onJumpToStep(selectedStep.step_id);
                        onOpenChange(false);
                      }}
                      size="sm"
                      variant="outline"
                    >
                      回到步骤配置
                      <ArrowUpRight />
                    </Button>
                  </div>

                  <Tabs className="mt-4" defaultValue={selectedStep.status === "failed" ? "failure" : "response"}>
                    <TabsList variant="line">
                      <TabsTrigger value="failure">结果</TabsTrigger>
                      <TabsTrigger value="request">请求</TabsTrigger>
                      <TabsTrigger value="response">响应</TabsTrigger>
                      <TabsTrigger value="assertions">断言</TabsTrigger>
                      <TabsTrigger value="variables">变量</TabsTrigger>
                      <TabsTrigger value="attempts">尝试</TabsTrigger>
                    </TabsList>
                    <TabsContent value="failure">
                      <FailureView step={selectedStep} />
                    </TabsContent>
                    <TabsContent value="request">
                      <JsonView value={{ request: selectedStep.request, inputs: selectedStep.inputs }} />
                    </TabsContent>
                    <TabsContent value="response">
                      <JsonView value={selectedStep.response} />
                    </TabsContent>
                    <TabsContent value="assertions">
                      <JsonView value={selectedStep.assertions} />
                    </TabsContent>
                    <TabsContent value="variables">
                      <JsonView value={{ inputs: selectedStep.inputs, outputs: selectedStep.outputs }} />
                    </TabsContent>
                    <TabsContent value="attempts">
                      <JsonView value={selectedStep.attempts} />
                    </TabsContent>
                  </Tabs>
                </main>
              </div>
            ) : null}
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}

function FailureView({ step }: { step: ApiAutomationScenarioStepResult }) {
  const message = step.error || step.skip_reason || "步骤执行通过，未发现异常。";
  return (
    <div
      className={cn(
        "mt-4 rounded-xl border p-4 text-sm",
        step.status === "failed" ? "border-red-200 bg-red-50 text-red-800" : "bg-muted/30",
      )}
    >
      {message}
    </div>
  );
}

function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="mt-4 max-h-64 overflow-auto rounded-xl bg-slate-950 p-4 font-mono text-[11px] text-slate-200 leading-5">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const passed = status === "passed";
  const failed = ["failed", "cancelled", "interrupted"].includes(status);
  return (
    <Badge
      className={cn(passed && "bg-emerald-50 text-emerald-700", failed && "bg-red-50 text-red-700")}
      variant="secondary"
    >
      {passed ? "运行通过" : failed ? "运行失败" : "运行中"}
    </Badge>
  );
}

function StepStatusIcon({ status }: { status: ApiAutomationScenarioStepResult["status"] }) {
  if (status === "passed") return <CheckCircle2 className="size-4 text-emerald-600" />;
  if (status === "failed") return <XCircle className="size-4 text-red-600" />;
  if (status === "skipped") return <Clock3 className="size-4 text-slate-400" />;
  return <CircleDashed className="size-4 text-sky-600" />;
}

function stepStatusLabel(status: ApiAutomationScenarioStepResult["status"]) {
  return { passed: "通过", failed: "失败", skipped: "未执行", pending: "等待中" }[status];
}
