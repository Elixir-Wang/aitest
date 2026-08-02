"use client";

import { useEffect, useState } from "react";

import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Copy,
  Lightbulb,
  RotateCcw,
  SearchCheck,
  Wrench,
  X,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  ApiAutomationScenarioRunResult,
  ApiAutomationScenarioStep,
  ApiAutomationScenarioStepResult,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

type ApiScenarioRunDrawerProps = {
  busy: boolean;
  open: boolean;
  result: ApiAutomationScenarioRunResult | null;
  runId: string;
  status: string;
  stepConfigs: ApiAutomationScenarioStep[];
  onOpenChange: (open: boolean) => void;
  onJumpToStep: (stepId: string) => void;
  onRerun: () => void;
};

export function ApiScenarioRunDrawer({
  busy,
  open,
  result,
  runId,
  status,
  stepConfigs,
  onOpenChange,
  onJumpToStep,
  onRerun,
}: ApiScenarioRunDrawerProps) {
  const [selectedStepId, setSelectedStepId] = useState("");
  const effectiveStatus = result?.status ?? status;
  const failed = isFailedStatus(effectiveStatus);

  useEffect(() => {
    const firstFailedStep = result?.steps.find((step) => step.status === "failed");
    setSelectedStepId(firstFailedStep?.step_id ?? result?.steps[0]?.step_id ?? "");
  }, [result]);

  const selectedStep = result?.steps.find((step) => step.step_id === selectedStepId) ?? result?.steps[0] ?? null;
  const selectedStepConfig = stepConfigs.find((step) => step.id === selectedStep?.step_id) ?? null;
  const passedCount = result?.steps.filter((step) => step.status === "passed").length ?? 0;
  const failedCount = result?.steps.filter((step) => step.status === "failed").length ?? 0;

  return (
    <Drawer direction="right" handleOnly onOpenChange={onOpenChange} open={open}>
      <DrawerContent className="grid h-full w-full grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden rounded-none bg-background p-0 data-[vaul-drawer-direction=right]:w-[min(96vw,760px)] data-[vaul-drawer-direction=right]:sm:max-w-[760px]">
        <DrawerHeader className="border-b bg-background px-5 py-4 text-left">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <DrawerTitle className="font-semibold text-base">运行结果</DrawerTitle>
                <RunStatusBadge status={effectiveStatus} />
              </div>
              <p className="mt-1.5 truncate font-mono text-[11px] text-muted-foreground">{runId || "等待运行记录"}</p>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {runId ? (
                <Button disabled={busy} onClick={onRerun} size="icon-sm" title="重新运行" variant="ghost">
                  <RotateCcw className={cn("size-4", busy && "animate-spin")} />
                </Button>
              ) : null}
              <DrawerClose asChild>
                <Button aria-label="关闭运行结果" size="icon-sm" title="关闭" variant="ghost">
                  <X className="size-4" />
                </Button>
              </DrawerClose>
            </div>
          </div>
        </DrawerHeader>

        <RunSummary
          duration={normalizeDuration(result?.duration_ms)}
          failed={failed}
          failedCount={failedCount}
          passedCount={passedCount}
          result={result}
          selectedStep={selectedStep}
        />

        {!result ? (
          <div className="grid min-h-0 place-items-center bg-muted/10 px-8">
            <div className="max-w-xs text-center">
              <div className="mx-auto grid size-11 place-items-center rounded-full border border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                <CircleDashed className="size-5 animate-spin" />
              </div>
              <div className="mt-4 font-medium">正在执行场景</div>
              <p className="mt-1.5 text-muted-foreground text-sm leading-6">
                步骤完成后会自动定位失败位置，并展示请求、响应和断言详情。
              </p>
            </div>
          </div>
        ) : selectedStep ? (
          <div className="grid min-h-0 grid-rows-[minmax(150px,34vh)_minmax(0,1fr)] overflow-hidden sm:grid-cols-[220px_minmax(0,1fr)] sm:grid-rows-1">
            <aside className="min-h-0 overflow-y-auto border-b bg-muted/15 px-3 py-4 sm:border-r sm:border-b-0">
              <div className="mb-3 flex items-center justify-between px-2">
                <span className="font-medium text-[11px] text-muted-foreground">执行步骤</span>
                <span className="font-mono text-[10px] text-muted-foreground">{result.steps.length}</span>
              </div>
              <div className="relative space-y-1 before:absolute before:top-4 before:bottom-4 before:left-[23px] before:w-px before:bg-border">
                {result.steps.map((step, index) => (
                  <button
                    className={cn(
                      "relative flex w-full items-center gap-2.5 rounded-md py-2 pr-2 pl-1.5 text-left transition-colors",
                      selectedStep.step_id === step.step_id
                        ? step.status === "failed"
                          ? "bg-red-50 text-red-950 dark:bg-red-500/10 dark:text-red-100"
                          : "bg-background shadow-xs"
                        : "hover:bg-background/70",
                    )}
                    key={step.step_id}
                    onClick={() => setSelectedStepId(step.step_id)}
                    type="button"
                  >
                    <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full border bg-background">
                      <StepStatusIcon status={step.status} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-xs">{step.name}</span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <span>{String(index + 1).padStart(2, "0")}</span>
                        <span>·</span>
                        <span>{stepStatusLabel(step.status)}</span>
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </aside>

            <main className="min-h-0 min-w-0 overflow-y-auto px-4 py-4 sm:px-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate font-semibold text-sm">{selectedStep.name}</h3>
                    {selectedStep.step_type ? (
                      <Badge className="font-mono text-[10px]" variant="outline">
                        {selectedStep.step_type}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {stepStatusLabel(selectedStep.status)} · {formatDuration(selectedStep.duration_ms)}
                  </p>
                </div>
                <Button
                  className="shrink-0"
                  onClick={() => {
                    onJumpToStep(selectedStep.step_id);
                    onOpenChange(false);
                  }}
                  size="sm"
                  title="在画布中定位并打开步骤配置"
                  variant="outline"
                >
                  定位节点
                  <ArrowUpRight className="size-3.5" />
                </Button>
              </div>

              <Tabs
                className="mt-4 min-w-0"
                defaultValue={
                  selectedStep.status === "failed" || selectedStep.status === "skipped" ? "result" : "response"
                }
                key={selectedStep.step_id}
              >
                <div className="overflow-x-auto border-b">
                  <TabsList className="w-max min-w-full justify-start" variant="line">
                    <TabsTrigger value="result">结果</TabsTrigger>
                    <TabsTrigger value="request">请求</TabsTrigger>
                    <TabsTrigger value="response">响应</TabsTrigger>
                    <TabsTrigger value="assertions">断言</TabsTrigger>
                    <TabsTrigger value="variables">变量</TabsTrigger>
                    <TabsTrigger value="attempts">尝试</TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent value="result">
                  <FailureView configuredStep={selectedStepConfig} step={selectedStep} />
                </TabsContent>
                <TabsContent value="request">
                  <JsonView value={{ request: selectedStep.request ?? {}, inputs: selectedStep.inputs ?? {} }} />
                </TabsContent>
                <TabsContent value="response">
                  <JsonView value={selectedStep.response ?? {}} />
                </TabsContent>
                <TabsContent value="assertions">
                  <JsonView value={selectedStep.assertions ?? selectedStepConfig?.assertions ?? []} />
                </TabsContent>
                <TabsContent value="variables">
                  <JsonView value={{ inputs: selectedStep.inputs ?? {}, outputs: selectedStep.outputs ?? {} }} />
                </TabsContent>
                <TabsContent value="attempts">
                  <JsonView value={selectedStep.attempts ?? []} />
                </TabsContent>
              </Tabs>
            </main>
          </div>
        ) : (
          <div className="grid place-items-center text-muted-foreground text-sm">本次运行没有步骤结果</div>
        )}
      </DrawerContent>
    </Drawer>
  );
}

function RunSummary({
  duration,
  failed,
  failedCount,
  passedCount,
  result,
  selectedStep,
}: {
  duration: number | null;
  failed: boolean;
  failedCount: number;
  passedCount: number;
  result: ApiAutomationScenarioRunResult | null;
  selectedStep: ApiAutomationScenarioStepResult | null;
}) {
  const headline = result
    ? failed
      ? selectedStep?.status === "failed"
        ? `失败于 ${selectedStep.name}`
        : "场景运行失败"
      : "全部步骤运行通过"
    : "运行进度采集中";
  const description = result
    ? failed
      ? selectedStep?.error || selectedStep?.skip_reason || "选择失败步骤查看具体原因。"
      : "请求、响应、断言和变量结果已生成。"
    : "抽屉会在执行完成后自动更新。";

  return (
    <section
      className={cn(
        "border-b px-5 py-4",
        result && failed && "border-red-200 bg-red-50/70 dark:border-red-500/25 dark:bg-red-500/8",
        result && !failed && "border-emerald-200 bg-emerald-50/60 dark:border-emerald-500/25 dark:bg-emerald-500/8",
        !result && "bg-sky-50/60 dark:bg-sky-500/8",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 grid size-8 shrink-0 place-items-center rounded-full border bg-background",
            result && failed && "border-red-200 text-red-600 dark:border-red-500/30 dark:text-red-300",
            result && !failed && "border-emerald-200 text-emerald-600 dark:border-emerald-500/30 dark:text-emerald-300",
            !result && "border-sky-200 text-sky-600 dark:border-sky-500/30 dark:text-sky-300",
          )}
        >
          {result ? (
            failed ? (
              <XCircle className="size-4" />
            ) : (
              <CheckCircle2 className="size-4" />
            )
          ) : (
            <Clock3 className="size-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm">{headline}</div>
          <p className="mt-1 line-clamp-2 text-muted-foreground text-xs leading-5">{description}</p>
          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 font-mono text-[10px] text-muted-foreground">
            <span>{result ? `${passedCount}/${result.steps.length} 步通过` : "等待步骤结果"}</span>
            {failedCount > 0 ? <span className="text-red-700 dark:text-red-300">{failedCount} 个失败</span> : null}
            <span>{duration === null ? "-- ms" : formatDuration(duration)}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function FailureView({
  configuredStep,
  step,
}: {
  configuredStep: ApiAutomationScenarioStep | null;
  step: ApiAutomationScenarioStepResult;
}) {
  const [copied, setCopied] = useState(false);
  const message = firstNonEmpty(step.error, step.skip_reason) ?? "步骤执行通过，未发现异常。";
  const hasRecordedError = Boolean(step.error?.trim()) || Boolean(step.skip_reason?.trim());
  const failed = step.status === "failed";
  const diagnosis = buildFailureDiagnosis(step, configuredStep);

  async function copyMessage() {
    await navigator.clipboard.writeText(message);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="space-y-5 pt-4">
      {failed ? (
        <section className="border-y bg-muted/10 py-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <div className="grid size-8 shrink-0 place-items-center rounded-full border border-red-200 bg-red-50 text-red-600 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
                <SearchCheck className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-semibold text-sm">{diagnosis.title}</h4>
                  <Badge
                    className={cn(
                      "text-[10px]",
                      diagnosis.confidence === "high"
                        ? "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-200"
                        : "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200",
                    )}
                    variant="secondary"
                  >
                    {diagnosis.confidence === "high" ? "高置信度" : "需要更多证据"}
                  </Badge>
                </div>
                <p className="mt-2 text-foreground/80 text-xs leading-6">{diagnosis.conclusion}</p>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {failed ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <DiagnosisSection icon={AlertCircle} items={diagnosis.evidence} title="已确认事实" />
          <DiagnosisSection icon={Lightbulb} items={diagnosis.causes} title="最可能原因" />
        </div>
      ) : null}

      {failed ? <DiagnosisSection icon={Wrench} items={diagnosis.actions} ordered title="建议处理" /> : null}

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h4 className="font-medium text-muted-foreground text-xs">原始错误</h4>
          {hasRecordedError ? (
            <Button onClick={() => void copyMessage()} size="sm" title="复制错误信息" variant="ghost">
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? "已复制" : "复制"}
            </Button>
          ) : null}
        </div>
        <pre
          className={cn(
            "whitespace-pre-wrap break-words border-l-2 py-2 pr-3 pl-4 font-mono text-[11px] leading-6",
            failed
              ? "border-red-500 bg-red-50/50 text-red-800 dark:bg-red-500/8 dark:text-red-200"
              : step.status === "skipped"
                ? "border-slate-300 text-muted-foreground"
                : "border-emerald-500 text-emerald-800 dark:text-emerald-200",
          )}
        >
          {message}
        </pre>
      </section>
    </div>
  );
}

function DiagnosisSection({
  icon: Icon,
  items,
  ordered = false,
  title,
}: {
  icon: typeof AlertCircle;
  items: string[];
  ordered?: boolean;
  title: string;
}) {
  const List = ordered ? "ol" : "ul";
  return (
    <section>
      <div className="flex items-center gap-2 font-medium text-xs">
        <Icon className="size-3.5 text-muted-foreground" />
        {title}
      </div>
      <List className={cn("mt-2 space-y-2 text-foreground/75 text-xs leading-5", ordered && "list-decimal pl-4")}>
        {items.map((item) => (
          <li
            className={cn(
              !ordered &&
                "flex gap-2 before:mt-2 before:size-1 before:shrink-0 before:rounded-full before:bg-muted-foreground/60",
            )}
            key={item}
          >
            {item}
          </li>
        ))}
      </List>
    </section>
  );
}

function JsonView({ value }: { value: unknown }) {
  const empty =
    value == null ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "object" && Object.keys(value).length === 0);
  if (empty) return <div className="py-10 text-center text-muted-foreground text-xs">暂无数据</div>;
  return (
    <pre className="mt-4 overflow-auto bg-slate-950 p-4 font-mono text-[11px] text-slate-200 leading-5">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function RunStatusBadge({ status }: { status: string }) {
  const passed = status === "passed";
  const failed = isFailedStatus(status);
  return (
    <Badge
      className={cn(
        passed && "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200",
        failed && "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-200",
        !passed && !failed && "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-200",
      )}
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

type FailureDiagnosis = {
  title: string;
  conclusion: string;
  confidence: "high" | "medium";
  evidence: string[];
  causes: string[];
  actions: string[];
};

function buildFailureDiagnosis(
  step: ApiAutomationScenarioStepResult,
  configuredStep: ApiAutomationScenarioStep | null,
): FailureDiagnosis {
  const message = firstNonEmpty(step.error, step.skip_reason) ?? "步骤执行失败";
  const assertionFailure = message.match(/^路径\s+(.+?):\s*期望\s+(.+?),\s*实际\s+(.+)$/);
  const responseBody = getResponseBody(step.response);
  const hasResponseEvidence = responseBody !== undefined;
  const statusAssertion = configuredStep?.assertions.find((assertion) => assertion.type === "status_code");

  if (assertionFailure) {
    const [, path, expected, reportedActual] = assertionFailure;
    const actual = hasResponseEvidence ? readResponsePath(responseBody, path) : undefined;
    const targetKey = path.split("/").filter(Boolean).at(-1) ?? "";
    const alternatePaths = hasResponseEvidence && targetKey ? findKeyPaths(responseBody, targetKey) : [];
    const configuredAssertion = configuredStep?.assertions.find(
      (assertion) => assertion.type === "jsonpath_equals" && assertion.path === path,
    );

    if (alternatePaths.length > 0 && actual == null) {
      return {
        title: "断言路径与实际响应结构不一致",
        conclusion: `响应中存在字段 ${targetKey}，但不在当前断言路径 ${path}。最接近的位置是 ${alternatePaths[0]}。`,
        confidence: "high",
        evidence: compactItems([
          statusAssertion
            ? `HTTP 状态码断言 ${String(statusAssertion.expected)} 已通过，失败发生在业务字段校验。`
            : "失败发生在业务字段校验阶段。",
          `当前断言要求 ${path} 等于 ${expected}。`,
          `运行时 ${path} 解析结果为 ${formatUnknown(actual ?? reportedActual)}。`,
          `实际响应中检测到候选字段：${alternatePaths.slice(0, 3).join("、")}。`,
        ]),
        causes: ["接口响应层级发生变化，但场景断言仍沿用旧路径。", "接口文档与生产环境的真实响应结构没有同步。"],
        actions: [
          `将断言路径从 ${path} 调整为实际字段路径，并同步检查响应提取器。`,
          "更新接口资产中的响应示例或 Schema。",
          "重新运行当前步骤验证业务码和下游变量提取。",
        ],
      };
    }

    if (actual != null) {
      return {
        title: "业务字段值与预期不一致",
        conclusion: `${path} 字段存在，期望值为 ${expected}，实际返回 ${formatUnknown(actual)}。`,
        confidence: "high",
        evidence: compactItems([
          statusAssertion
            ? `HTTP 状态码断言 ${String(statusAssertion.expected)} 已通过，失败发生在业务字段校验。`
            : "失败发生在业务字段校验阶段。",
          `业务断言配置为 ${path} = ${String(configuredAssertion?.expected ?? expected)}。`,
          `运行时报告的实际值为 ${reportedActual}。`,
          `响应证据中 ${path} 的解析值为 ${formatUnknown(actual)}。`,
        ]),
        causes: [
          "请求参数或业务前置条件不满足，接口通过业务码返回失败。",
          "场景断言中的成功业务码与接口当前契约不一致。",
          "接口返回了 HTTP 200，但响应体表达的是业务失败。",
        ],
        actions: [
          "查看“响应”页中的 message，确认具体业务错误原因。",
          "对照接口契约检查本步骤的请求参数和业务前置条件。",
          "修正请求后重新运行；仅在契约确认变更时调整业务码断言。",
        ],
      };
    }

    return {
      title: "响应缺少断言要求的业务字段",
      conclusion: hasResponseEvidence
        ? `接口返回成功状态后，响应 JSON 中没有可用于 ${path} 断言的值，实际解析结果为 ${formatUnknown(actual)}。`
        : `当前运行已进入 ${path} 业务断言，但旧运行记录没有保存响应体，暂时无法确认字段缺失还是响应层级变化。`,
      confidence: hasResponseEvidence ? "high" : "medium",
      evidence: compactItems([
        statusAssertion ? `HTTP 状态码断言 ${String(statusAssertion.expected)} 已通过。` : "请求已经进入响应断言阶段。",
        `业务断言配置为 ${path} = ${String(configuredAssertion?.expected ?? expected)}。`,
        `运行时报告的实际值为 ${reportedActual}。`,
        hasResponseEvidence
          ? `响应证据中 ${path} 的解析值为 ${formatUnknown(actual)}。`
          : "本次旧运行未保存响应体、请求快照和步骤耗时。",
      ]),
      causes: hasResponseEvidence
        ? [
            "生产接口响应结构与接口契约不一致。",
            "接口返回了 HTTP 200，但响应体是另一种业务错误或降级结构。",
            "断言路径已过期或字段名称发生变化。",
          ]
        : [
            "响应中的 code 字段可能被移动到其他层级。",
            "接口可能返回 HTTP 200 的业务错误结构。",
            "当前 /code 断言可能与真实响应契约不一致。",
          ],
      actions: hasResponseEvidence
        ? [
            "查看“响应”页确认真实 JSON 结构和业务错误信息。",
            "根据真实响应修正断言路径或推动接口恢复契约。",
            "同步检查 /data/segment_code 提取器，避免修复断言后在下一阶段继续失败。",
          ]
        : [
            "重新运行一次以采集完整、已脱敏的请求和响应证据。",
            "在“响应”页确认 code 的真实位置和业务 message。",
            "证据确认后再修改断言或接口实现，不建议直接删除业务断言。",
          ],
    };
  }

  return {
    title: "步骤执行异常",
    conclusion: message,
    confidence: hasResponseEvidence ? "high" : "medium",
    evidence: compactItems([
      step.response?.status_code != null
        ? `HTTP 状态码为 ${String(step.response.status_code)}。`
        : "运行记录没有提供 HTTP 状态码。",
      step.attempts?.length ? `共执行 ${step.attempts.length} 次尝试。` : "没有可用的重试记录。",
    ]),
    causes: ["请求配置、接口响应或断言执行过程中发生异常。", "需要结合请求、响应和尝试记录缩小范围。"],
    actions: [
      "先查看请求和响应页中的完整证据。",
      "检查运行环境、鉴权变量和请求参数。",
      "修正后仅重新运行当前场景验证。",
    ],
  };
}

function getResponseBody(response: Record<string, unknown> | undefined) {
  if (!response || Object.keys(response).length === 0) return undefined;
  return "body" in response ? response.body : response;
}

function readResponsePath(value: unknown, path: string): unknown {
  if (!path || path === "$" || path === "/") return value;
  const tokens = path.startsWith("/")
    ? path
        .slice(1)
        .split("/")
        .filter(Boolean)
        .map((token) => token.replaceAll("~1", "/").replaceAll("~0", "~"))
    : path
        .replace(/^\$\.?/, "")
        .replaceAll("[", ".")
        .replaceAll("]", "")
        .split(".")
        .filter(Boolean);
  let current = value;
  for (const token of tokens) {
    if (Array.isArray(current) && /^\d+$/.test(token)) current = current[Number(token)];
    else if (current && typeof current === "object") current = (current as Record<string, unknown>)[token];
    else return undefined;
  }
  return current;
}

function findKeyPaths(value: unknown, targetKey: string, path = "", depth = 0): string[] {
  if (depth > 5 || value == null || typeof value !== "object") return [];
  const matches: string[] = [];
  for (const [key, child] of Object.entries(value)) {
    const childPath = `${path}/${key}`;
    if (key === targetKey) matches.push(childPath);
    if (matches.length < 3) matches.push(...findKeyPaths(child, targetKey, childPath, depth + 1));
    if (matches.length >= 3) break;
  }
  return matches.slice(0, 3);
}

function compactItems(items: Array<string | false | null | undefined>) {
  return items.filter((item): item is string => Boolean(item));
}

function firstNonEmpty(...values: Array<string | null | undefined>) {
  return values.find((value) => Boolean(value?.trim()));
}

function formatUnknown(value: unknown) {
  if (value === undefined) return "未记录";
  if (value === null) return "None";
  if (typeof value === "string") return value || "空字符串";
  return JSON.stringify(value);
}

function isFailedStatus(status: string) {
  return ["failed", "cancelled", "interrupted"].includes(status);
}

function normalizeDuration(duration: number | null | undefined) {
  return typeof duration === "number" && Number.isFinite(duration) ? duration : null;
}

function formatDuration(duration: number | null | undefined) {
  if (typeof duration !== "number" || !Number.isFinite(duration)) return "-- ms";
  if (duration >= 1000) return `${(duration / 1000).toFixed(duration >= 10_000 ? 1 : 2)} s`;
  return `${Math.round(duration)} ms`;
}
