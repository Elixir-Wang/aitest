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
  Play,
  RefreshCw,
  Save,
  ShieldCheck,
} from "lucide-react";
import { codeToTokens } from "shiki";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiRequestError,
  confirmPerformanceScript,
  createPerformanceRun,
  getPerformanceScript,
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

  const loadScript = useCallback(() => {
    setLoadError(false);
    setScript(null);
    return getPerformanceScript(projectId, testId)
      .then((result) => {
        setScript(result);
        const preview = result.runtime_preview;
        const planRequest = (result.plan.request ?? {}) as { headers?: unknown; body?: unknown };
        const requestHeaders = preview?.request?.headers ?? planRequest.headers ?? {};
        const requestBody = preview?.request?.body ?? planRequest.body ?? null;
        const rules = preview?.success_rules ?? result.plan.success_rules ?? [];
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
        <p className="mt-1 max-w-sm text-muted-foreground text-xs leading-5">
          无法获取当前脚本，请检查网络后重试。
        </p>
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
    setSaving(true);
    try {
      const updated = await updatePerformanceScriptConfiguration(projectId, testId, scriptId, {
        request: { headers: JSON.parse(headers), body: JSON.parse(body) },
        success_rules: JSON.parse(successRules),
      });
      setScript(updated);
      const preview = updated.runtime_preview;
      const planRequest = (updated.plan.request ?? {}) as { headers?: unknown; body?: unknown };
      setHeaders(JSON.stringify(preview?.request?.headers ?? planRequest.headers ?? {}, null, 2));
      setBody(JSON.stringify(preview?.request?.body ?? planRequest.body ?? null, null, 2));
      setSuccessRules(JSON.stringify(preview?.success_rules ?? updated.plan.success_rules ?? [], null, 2));
      toast.success("脚本配置已重新渲染并校验");
    } catch (error) {
      toast.error(error instanceof SyntaxError ? "配置必须是有效 JSON" : apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    setSaving(true);
    try {
      const updated = await confirmPerformanceScript(projectId, testId, scriptId);
      setScript(updated);
      toast.success("脚本已确认，可用于正式压测");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function startRun() {
    setSaving(true);
    try {
      const run = await createPerformanceRun(projectId, testId, scriptId);
      router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${run.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-lg border bg-card">
        <div className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileCode2 className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-semibold text-base">当前脚本</h1>
                <Badge
                  className={
                    script.validation_result.valid
                      ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                      : undefined
                  }
                  variant={script.validation_result.valid ? "secondary" : "destructive"}
                >
                  {script.validation_result.valid ? <CheckCircle2 className="size-3" /> : null}
                  {statusLabel(script.validation_status)}
                </Badge>
              </div>
              <p className="mt-1 truncate text-muted-foreground text-xs">生成来源：{script.generation_source}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:justify-end">
            <Button disabled={saving || !script.validation_result.valid} onClick={confirm}>
              {saving ? <LoaderCircle className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
              确认脚本
            </Button>
            {script.validation_status === "confirmed" ? (
              <Button disabled={saving} onClick={startRun}>
                {saving ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="size-4 fill-current" />}
                进入 Locust 控制台
                <ChevronRight className="size-4" />
              </Button>
            ) : null}
          </div>
        </div>
        <div className="flex items-start gap-2 border-t bg-muted/35 px-4 py-2.5 text-xs sm:items-center sm:px-5">
          {script.validation_result.valid ? (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 sm:mt-0 dark:text-emerald-400" />
          ) : (
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive sm:mt-0" />
          )}
          <span className={script.validation_result.valid ? "text-foreground" : "text-destructive"}>
            {script.validation_result.valid
              ? "结构、语法和安全校验均已通过，脚本可以进入执行阶段。"
              : "当前脚本未通过校验，请修正左侧配置后重新校验。"}
          </span>
        </div>
      </section>

      <div className="grid gap-4 xl:h-[calc(100dvh-14rem)] xl:max-h-[52rem] xl:min-h-[36rem] xl:grid-cols-[minmax(19rem,0.78fr)_minmax(0,1.22fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border bg-card">
          <div className="flex items-start justify-between gap-4 border-b px-4 py-3.5">
            <div>
              <div className="flex items-center gap-2">
                <Braces className="size-4 text-muted-foreground" />
                <h2 className="font-semibold text-sm">结构化请求配置</h2>
              </div>
              <p className="mt-1 text-muted-foreground text-xs leading-5">
                已确认脚本也可直接调整；保存后需要重新确认才能运行。
              </p>
            </div>
            <Button disabled={saving} onClick={saveConfiguration} size="sm" variant="outline">
              {saving ? <LoaderCircle className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              保存并校验
            </Button>
          </div>
          <div className="min-h-0 flex-1 divide-y overflow-y-auto">
            <JsonField disabled={false} label="Headers" onChange={setHeaders} value={headers} />
            <JsonField disabled={false} label="Body" onChange={setBody} value={body} />
            <JsonField disabled={false} label="成功规则" onChange={setSuccessRules} rows={9} value={successRules} />
          </div>
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

        <section className="flex min-h-[36rem] min-w-0 flex-col overflow-hidden rounded-lg border bg-card xl:min-h-0">
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
    </div>
  );
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

function statusLabel(status: PerformanceScript["validation_status"]) {
  return {
    generating: "生成中",
    validation_failed: "校验失败",
    pending_confirmation: "待确认",
    confirmed: "已确认",
  }[status];
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "脚本操作失败";
}
