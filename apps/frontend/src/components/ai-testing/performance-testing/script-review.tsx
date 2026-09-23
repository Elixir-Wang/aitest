"use client";

import { type CSSProperties, useCallback, useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import {
  AlertCircle,
  Braces,
  CheckCircle2,
  ChevronRight,
  FileCode2,
  LoaderCircle,
  PanelRightOpen,
  Play,
  RefreshCw,
  Save,
} from "lucide-react";
import { codeToTokens } from "shiki";

import { Button } from "@/components/ui/button";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiRequestError,
  ensurePerformanceRun,
  getPerformanceScript,
  type PerformanceScenarioStep,
  type PerformanceScript,
  updatePerformanceScriptConfiguration,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

export function ScriptReview({ projectId, testId, scriptId }: { projectId: string; testId: string; scriptId: string }) {
  const router = useRouter();
  const [script, setScript] = useState<PerformanceScript | null>(null);
  const [headers, setHeaders] = useState("{}");
  const [body, setBody] = useState("null");
  const [successRules, setSuccessRules] = useState("[]");
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [selectedStep, setSelectedStep] = useState<PerformanceScenarioStep | null>(null);

  const loadScript = useCallback(() => {
    setLoadError(false);
    setScript(null);
    return getPerformanceScript(projectId, testId)
      .then((result) => {
        setScript(result);
        const preview = result.runtime_preview;
        const planRequest = (result.plan.request ?? {}) as { headers?: unknown; body?: unknown };
        const requestPreview = preview && "request" in preview ? preview : null;
        const requestHeaders = requestPreview?.request.headers ?? planRequest.headers ?? {};
        const requestBody = requestPreview?.request.body ?? planRequest.body ?? null;
        const rules = requestPreview?.success_rules ?? result.plan.success_rules ?? [];
        setHeaders(JSON.stringify(requestHeaders, null, 2));
        setBody(JSON.stringify(requestBody, null, 2));
        setSuccessRules(JSON.stringify(rules, null, 2));
      })
      .catch((error) => {
        setLoadError(true);
        toast.error(apiErrorMessage(error));
      });
  }, [projectId, testId]);

  useEffect(() => {
    void loadScript();
  }, [loadScript]);

  if (loadError) {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center rounded-lg border bg-card px-6 text-center">
        <div className="mb-4 flex size-11 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
          <AlertCircle className="size-5" />
        </div>
        <h2 className="font-semibold text-sm">脚本加载失败</h2>
        <p className="mt-1 max-w-sm text-muted-foreground text-xs leading-5">无法获取当前脚本，请检查网络后重试。</p>
        <Button className="mt-5" onClick={() => void loadScript()} variant="outline">
          <RefreshCw className="size-4" />
          重新加载
        </Button>
      </div>
    );
  }

  if (!script) {
    return (
      <div className="grid min-h-[36rem] gap-4 xl:grid-cols-[minmax(19rem,0.78fr)_minmax(0,1.22fr)]">
        <div className="animate-pulse rounded-lg border bg-card p-5">
          <div className="h-5 w-36 rounded bg-muted" />
          <div className="mt-3 h-3 w-56 rounded bg-muted" />
          <div className="mt-8 space-y-4">
            <div className="h-36 rounded-md bg-muted/70" />
            <div className="h-28 rounded-md bg-muted/70" />
            <div className="h-40 rounded-md bg-muted/70" />
          </div>
        </div>
        <div className="animate-pulse rounded-lg border bg-card p-5">
          <div className="h-5 w-32 rounded bg-muted" />
          <div className="mt-6 h-[30rem] rounded-md bg-muted/70" />
        </div>
      </div>
    );
  }
  async function saveConfiguration() {
    if (!script || script.plan.target_type === "scenario") return;
    setSaving(true);
    try {
      const updated = await updatePerformanceScriptConfiguration(projectId, testId, scriptId, {
        request: { headers: JSON.parse(headers), body: JSON.parse(body) },
        success_rules: JSON.parse(successRules),
      });
      setScript(updated);
      const preview = updated.runtime_preview;
      const planRequest = (updated.plan.request ?? {}) as { headers?: unknown; body?: unknown };
      const requestPreview = preview && "request" in preview ? preview : null;
      setHeaders(JSON.stringify(requestPreview?.request.headers ?? planRequest.headers ?? {}, null, 2));
      setBody(JSON.stringify(requestPreview?.request.body ?? planRequest.body ?? null, null, 2));
      setSuccessRules(JSON.stringify(requestPreview?.success_rules ?? updated.plan.success_rules ?? [], null, 2));
      toast.success("脚本配置已重新渲染并校验");
    } catch (error) {
      toast.error(error instanceof SyntaxError ? "配置必须是有效 JSON" : apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function startRun() {
    if (!script) return;
    setSaving(true);
    try {
      const run = await ensurePerformanceRun(projectId, testId, scriptId);
      router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${run.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <section className="flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-card text-muted-foreground">
            <FileCode2 className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-semibold text-sm">当前脚本</h1>
              <span
                className={
                  script.validation_result.valid
                    ? "inline-flex items-center gap-1 text-emerald-700 text-xs dark:text-emerald-400"
                    : "inline-flex items-center gap-1 text-destructive text-xs"
                }
              >
                {script.validation_result.valid ? (
                  <CheckCircle2 className="size-3.5" />
                ) : (
                  <AlertCircle className="size-3.5" />
                )}
                {script.validation_result.valid ? "校验通过" : "校验失败"}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 sm:justify-end">
          {!script.validation_result.valid ? (
            <span className="hidden text-destructive text-xs lg:inline">修正配置并通过校验后可运行</span>
          ) : null}
          <Button disabled={saving || !script.validation_result.valid} onClick={startRun}>
            {saving ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4 fill-current" />}
            进入 Locust 控制台
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </section>

      <div className="grid items-start gap-4 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <section
          className={
            script.plan.target_type === "scenario"
              ? "overflow-hidden rounded-lg border bg-card"
              : "flex min-h-[36rem] flex-col overflow-hidden rounded-lg border bg-card xl:h-[calc(100dvh-12rem)] xl:max-h-[54rem]"
          }
        >
          {script.plan.target_type === "endpoint" ? (
            <div className="flex items-start justify-between gap-4 border-b px-4 py-3.5">
              <div>
                <div className="flex items-center gap-2">
                  <Braces className="size-4 text-muted-foreground" />
                  <h2 className="font-semibold text-sm">结构化请求配置</h2>
                </div>
                <p className="mt-1 text-muted-foreground text-xs leading-5">
                  调整请求参数后保存，系统会重新生成脚本并执行校验。
                </p>
              </div>
              <Button disabled={saving} onClick={saveConfiguration} size="sm" variant="outline">
                {saving ? <LoaderCircle className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                保存并校验
              </Button>
            </div>
          ) : null}
          {script.plan.target_type === "scenario" ? (
            <div className="text-sm">
              <div className="border-b px-4 py-4">
                <p className="font-semibold text-base leading-6">{script.plan.scenario_name}</p>
                <div className="mt-2 flex items-center gap-2 text-muted-foreground text-xs">
                  <span className="font-mono text-foreground tabular-nums">
                    v{script.plan.scenario_revision ?? "-"}
                  </span>
                  <span className="h-3 w-px bg-border" />
                  <span className="tabular-nums">{script.plan.steps?.length ?? 0} 个步骤</span>
                </div>
              </div>
              <div className="border-b bg-muted/20 px-4 py-2.5 font-medium text-muted-foreground text-xs">执行顺序</div>
              <div className="px-4 py-3">
                {(script.plan.steps ?? []).map((step, index) => (
                  <div className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-3" key={String(step.id ?? index)}>
                    <div className="flex flex-col items-center">
                      <span className="mt-3 font-mono text-[11px] text-muted-foreground tabular-nums">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      {index < (script.plan.steps?.length ?? 0) - 1 ? (
                        <span className="mt-2 w-px flex-1 bg-border" />
                      ) : null}
                    </div>
                    <article className="min-w-0 border-b py-3 last:border-b-0">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-medium">{String(step.name ?? `步骤 ${index + 1}`)}</p>
                          {step.request ? (
                            <p className="mt-1.5 flex min-w-0 items-center gap-2 font-mono text-xs">
                              <span className="shrink-0 font-semibold text-foreground">
                                {String(step.request.method ?? "")}
                              </span>
                              <span className="truncate text-muted-foreground">{String(step.request.path ?? "")}</span>
                            </p>
                          ) : null}
                        </div>
                        <Button
                          className="-mt-1 -mr-1 h-7 shrink-0 px-2 text-xs"
                          onClick={() => setSelectedStep(step)}
                          size="sm"
                          variant="ghost"
                        >
                          <PanelRightOpen className="size-4" />
                          详情
                        </Button>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t pt-2.5 text-[11px] text-muted-foreground">
                        <StepMetric label="请求头" value={configCount(step.request?.headers)} />
                        <StepMetric
                          label="请求体"
                          value={
                            hasConfig(step.request?.body ?? step.request?.form ?? step.request?.multipart_form) ? 1 : 0
                          }
                        />
                        <StepMetric label="断言" value={configCount(step.assertions)} />
                        <StepMetric label="提取" value={configCount(step.extractors)} />
                      </div>
                    </article>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="min-h-0 flex-1 divide-y overflow-y-auto">
              <JsonField disabled={false} label="Headers" onChange={setHeaders} value={headers} />
              <JsonField disabled={false} label="Body" onChange={setBody} value={body} />
              <JsonField disabled={false} label="成功规则" onChange={setSuccessRules} rows={9} value={successRules} />
            </div>
          )}
          {(script.validation_result.errors ?? []).length > 0 ? (
            <div className="space-y-1 border-t bg-destructive/5 px-4 py-3">
              {(script.validation_result.errors ?? []).map((error) => (
                <p className="flex gap-2 text-destructive text-xs leading-5" key={error}>
                  <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
                  {error}
                </p>
              ))}
            </div>
          ) : null}
        </section>

        <section className="flex min-h-[36rem] min-w-0 flex-col overflow-hidden rounded-lg border bg-card xl:h-[calc(100dvh-12rem)] xl:max-h-[54rem]">
          <div className="flex items-center justify-between gap-3 border-b px-4 py-3.5">
            <div className="flex min-w-0 items-center gap-2">
              <FileCode2 className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0">
                <h2 className="font-semibold text-sm">只读 Locust 脚本</h2>
                <p className="mt-0.5 truncate text-[11px] text-muted-foreground">由结构化配置生成，不可直接编辑</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <OneClipboard copiedLabel="已复制" label="复制" text={script.code} />
              <span className="rounded border bg-muted px-2 py-1 font-mono text-[10px] text-muted-foreground">
                Python
              </span>
            </div>
          </div>
          <PythonCodeBlock code={script.code} />
        </section>
      </div>

      <Sheet onOpenChange={(open) => !open && setSelectedStep(null)} open={selectedStep !== null}>
        <SheetContent
          className="w-full gap-0 overflow-y-auto data-[side=right]:sm:max-w-3xl"
          side="right"
        >
          <SheetHeader className="border-b px-5 py-4 pr-14">
            <SheetTitle>{selectedStep?.name ?? "步骤详情"}</SheetTitle>
            <SheetDescription className="font-mono text-xs">
              {selectedStep?.request?.method ?? selectedStep?.step_type ?? ""} {selectedStep?.request?.path ?? ""}
            </SheetDescription>
          </SheetHeader>
          {selectedStep ? <ScenarioStepDetail step={selectedStep} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function StepMetric({ label, value }: { label: string; value: number }) {
  return (
    <span className={value > 0 ? "text-foreground" : undefined}>
      {label} <span className="font-mono tabular-nums">{value}</span>
    </span>
  );
}

function ScenarioStepDetail({ step }: { step: PerformanceScenarioStep }) {
  return (
    <div className="space-y-6 px-5 py-5 text-xs">
      <RequestDetail label="路径参数" value={step.request?.path_parameters} />
      <RequestDetail label="查询参数" value={step.request?.query_parameters} />
      <RequestDetail label="请求头" value={step.request?.headers} />
      <RequestDetail
        label={step.request?.multipart_form ? "请求体（multipart/form-data）" : "请求体"}
        value={step.request?.body ?? step.request?.form ?? step.request?.multipart_form}
      />
      <RequestDetail label="变量绑定" value={step.bindings} />
      <RequestDetail label="断言" value={step.assertions} />
      <RequestDetail label="提取器" value={step.extractors} />
    </div>
  );
}

function configCount(value: unknown) {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === "object") return Object.keys(value).length;
  return value === undefined || value === null || value === "" ? 0 : 1;
}

function hasConfig(value: unknown) {
  return configCount(value) > 0;
}

function PythonCodeBlock({ code }: { code: string }) {
  const [highlightedLines, setHighlightedLines] = useState<HighlightedLine[] | null>(null);

  useEffect(() => {
    let active = true;

    void codeToTokens(code, {
      lang: "python",
      themes: { light: "github-light", dark: "github-dark" },
      defaultColor: false,
    }).then(({ tokens }) => {
      if (active) {
        let lineOffset = 0;
        setHighlightedLines(
          tokens.map((line, number) => {
            const highlightedLine = {
              number: number + 1,
              offset: line[0]?.offset ?? lineOffset,
              tokens: line.map((token) => ({
                content: token.content,
                offset: token.offset,
                style: token.htmlStyle ?? {},
              })),
            };
            lineOffset += line.map((token) => token.content).join("").length + 1;
            return highlightedLine;
          }),
        );
      }
    });

    return () => {
      active = false;
    };
  }, [code]);

  if (!highlightedLines) {
    return (
      <pre className="min-h-0 flex-1 overflow-auto bg-[#fbfcfe] p-5 font-mono text-[13px] text-slate-800 leading-6 dark:bg-[#15191f] dark:text-slate-100">
        <code className="whitespace-pre">{code}</code>
      </pre>
    );
  }

  return (
    <pre className="min-h-0 flex-1 overflow-auto bg-[#fbfcfe] py-5 font-mono text-[13px] text-[color:var(--shiki-light)] leading-6 dark:bg-[#15191f] dark:text-[color:var(--shiki-dark)]">
      <code className="block w-max min-w-full">
        {highlightedLines.map((line) => (
          <span className="grid grid-cols-[3.25rem_minmax(max-content,1fr)] hover:bg-primary/[0.035]" key={line.offset}>
            <span className="sticky left-0 select-none border-slate-200 border-r bg-[#f4f7fa] px-3 text-right text-slate-400 dark:border-slate-700 dark:bg-[#1b2027] dark:text-slate-500">
              {line.number}
            </span>
            <span className="whitespace-pre px-5">
              {line.tokens.length === 0
                ? " "
                : line.tokens.map((token) => (
                    <span
                      className="text-[color:var(--shiki-light)] dark:text-[color:var(--shiki-dark)]"
                      key={token.offset}
                      style={token.style as CSSProperties}
                    >
                      {token.content}
                    </span>
                  ))}
            </span>
          </span>
        ))}
      </code>
    </pre>
  );
}

function RequestDetail({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null || (typeof value === "object" && Object.keys(value).length === 0)) {
    return null;
  }

  return (
    <div>
      <p className="mb-1 font-medium text-muted-foreground">{label}</p>
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded border bg-background p-2 font-mono text-[11px] leading-5">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

type HighlightedLine = {
  number: number;
  offset: number;
  tokens: Array<{ content: string; offset: number; style: Record<string, string> }>;
};

function JsonField({
  label,
  value,
  onChange,
  disabled,
  rows = 6,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  rows?: number;
}) {
  return (
    <div className="block px-4 py-3.5 text-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="font-medium text-xs">{label}</p>
        <span className="font-mono text-[10px] text-muted-foreground">JSON</span>
      </div>
      <Textarea
        className="bg-white font-mono text-xs dark:bg-[#24292e]"
        aria-readonly={disabled}
        onChange={(event) => onChange(event.target.value)}
        readOnly={disabled}
        rows={rows}
        spellCheck={false}
        value={value}
      />
    </div>
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "脚本操作失败";
}
