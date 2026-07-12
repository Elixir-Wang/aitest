"use client";

import { type ReactElement, type ReactNode, useEffect, useState } from "react";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, CheckCircle2, ClipboardCheck, Code2, Loader2, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type ApiAutomationTestCase, getApiAutomationTestCase } from "@/lib/api-client";
import { cn } from "@/lib/utils";

export default function ApiAutomationCaseDetailPage() {
  const params = useParams<{ projectId: string; caseId: string }>();
  const projectId = params.projectId;
  const caseId = params.caseId;
  const [testCase, setTestCase] = useState<ApiAutomationTestCase | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadCase() {
      try {
        setLoading(true);
        const detail = await getApiAutomationTestCase(projectId, caseId);
        if (!ignore) {
          setTestCase(detail);
        }
      } catch (error) {
        if (!ignore) {
          toast.error(error instanceof Error ? error.message : "接口用例详情加载失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadCase();

    return () => {
      ignore = true;
    };
  }, [projectId, caseId]);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目" },
        { label: "接口自动化", href: `/projects/${projectId}/automation/api` },
        { label: "接口用例详情" },
      ]}
      description="接口自动化用例详情"
      title="接口用例详情"
    >
      <ShellSection className="space-y-4">
        {loading ? (
          <div className="flex min-h-52 items-center justify-center text-muted-foreground text-sm">
            <Loader2 className="mr-2 size-4 animate-spin" />
            加载中
          </div>
        ) : testCase ? (
          <>
            <div className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={cn("border", apiCasePriorityTone(testCase.priority))} variant="outline">
                    {testCase.priority || "P2"}
                  </Badge>
                  <Badge variant="outline">{formatApiCaseCoverage(testCase.coverage)}</Badge>
                  <Badge
                    className="border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    variant="outline"
                  >
                    {testCase.source === "ai_generated" ? "AI 生成" : "人工维护"}
                  </Badge>
                </div>
                <h1 className="max-w-3xl break-words font-semibold text-2xl tracking-tight">{testCase.title}</h1>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button asChild className="h-9" size="sm" variant="outline">
                  <Link href={`/projects/${projectId}/automation/api?tab=cases`}>
                    <ArrowLeft className="size-4" />
                    返回列表
                  </Link>
                </Button>
                <Button
                  aria-label="刷新用例详情"
                  className="size-9"
                  disabled={loading}
                  onClick={() => window.location.reload()}
                  size="icon"
                  variant="outline"
                >
                  {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                  <span className="sr-only">刷新</span>
                </Button>
              </div>
            </div>
            <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 sm:p-5 dark:border-sky-900/70 dark:bg-sky-950/30">
              <div className="mb-2 flex items-center gap-2 font-medium text-sky-950 text-sm dark:text-sky-100">
                <ClipboardCheck className="size-4 text-sky-700 dark:text-sky-400" />
                测试描述
              </div>
              <p className="max-w-4xl whitespace-pre-wrap text-sky-950 text-sm leading-6 dark:text-sky-100">
                {testCase.test_description || "未补充测试描述"}
              </p>
            </div>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
              <ReviewBlock icon={<Code2 className="size-4" />} title="请求信息">
                {renderApiCaseRequest(testCase.request)}
              </ReviewBlock>
              <ReviewBlock icon={<ShieldAlert className="size-4" />} title="验证规则">
                {renderApiCaseAssertions(testCase.assertions)}
              </ReviewBlock>
            </div>
            {testCase.preconditions.length > 0 || Object.keys(testCase.test_data).length > 0 ? (
              <div className="grid gap-4 xl:grid-cols-2">
                {testCase.preconditions.length > 0 ? (
                  <ReviewBlock title="前置条件">{renderApiCasePreconditions(testCase.preconditions)}</ReviewBlock>
                ) : null}
                {Object.keys(testCase.test_data).length > 0 ? (
                  <ReviewBlock title="测试数据">{renderApiCaseTestData(testCase.test_data)}</ReviewBlock>
                ) : null}
              </div>
            ) : null}
            {testCase.assertions.length > 0 &&
            testCase.assertions.some((assertion) => hasValue(assertion.expected)) ? null : (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 text-sm dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-200">
                <ShieldAlert className="size-4 shrink-0" />
                当前用例尚未配置可执行的验证规则
              </div>
            )}
          </>
        ) : (
          <div className="flex min-h-52 items-center justify-center text-muted-foreground text-sm">接口用例不存在</div>
        )}
      </ShellSection>
    </PageShell>
  );
}

function ReviewBlock({ icon, title, children }: { icon?: ReactElement; title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border bg-card p-4 text-card-foreground shadow-[0_1px_2px_rgba(16,24,40,0.04)] sm:p-5 dark:shadow-none">
      <h3 className="mb-4 flex items-center gap-2 font-medium text-foreground text-sm">
        {icon ? <span className="text-sky-700 dark:text-sky-400">{icon}</span> : null}
        {title}
      </h3>
      <div className="whitespace-pre-wrap text-foreground text-sm leading-6">{children}</div>
    </section>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-transparent bg-muted/60 p-3 font-mono text-foreground text-xs dark:border-border dark:bg-muted/40">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

function renderApiCasePreconditions(preconditions: string[]) {
  return (
    <ul className="space-y-2">
      {preconditions.map((condition) => (
        <li className="flex gap-2" key={condition}>
          <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-slate-400" />
          <span>{condition}</span>
        </li>
      ))}
    </ul>
  );
}

function renderApiCaseRequest(request: Record<string, unknown>) {
  const method = asString(request.method) || "GET";
  const path = asString(request.path) || "/";
  const query = asRecord(request.query);
  const headers = asRecord(request.headers);
  const pathParams = asRecord(request.path_params);
  const body = request.body;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <MethodBadge method={method} />
        <code className="rounded bg-muted/60 px-2 py-1 text-foreground text-xs dark:bg-muted/40">{path}</code>
      </div>
      {Object.keys(pathParams).length > 0 ? <KeyValueBlock title="Path 参数" value={pathParams} /> : null}
      {Object.keys(query).length > 0 ? <KeyValueBlock title="Query 参数" value={query} /> : null}
      {Object.keys(headers).length > 0 ? <KeyValueBlock title="Headers 覆盖" value={headers} /> : null}
      {body !== undefined ? <KeyValueBlock title="Body" value={body} /> : null}
    </div>
  );
}

function renderApiCaseTestData(testData: Record<string, unknown>) {
  const entries = Object.entries(testData);
  if (entries.length === 0) {
    return <div className="text-muted-foreground text-sm">无独立测试数据说明</div>;
  }
  return (
    <div className="space-y-3">
      {entries.map(([name, rawValue]) => {
        const item = asRecord(rawValue);
        return (
          <div className="rounded-md border bg-muted/30 p-3 dark:bg-muted/20" key={name}>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="font-medium text-sm">{name}</div>
            </div>
            <InfoLine mono label="值" value={formatUnknown(Object.hasOwn(item, "value") ? item.value : rawValue)} />
          </div>
        );
      })}
    </div>
  );
}

function renderApiCaseAssertions(assertions: Record<string, unknown>[]) {
  if (assertions.length === 0) {
    return <div className="text-muted-foreground text-sm">暂无断言</div>;
  }
  return (
    <div className="space-y-3">
      {assertions
        .filter((assertion) => hasValue(assertion.expected))
        .map((assertion) => (
          <div
            className="flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 dark:border-emerald-900/70 dark:bg-emerald-950/30"
            key={JSON.stringify(assertion)}
          >
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <div className="min-w-0 space-y-1">
              <div className="font-medium text-emerald-950 text-sm dark:text-emerald-100">
                {formatAssertionType(asString(assertion.type))}
              </div>
              <div className="break-words font-mono text-emerald-900 text-xs dark:text-emerald-200">
                {formatAssertionDetail(assertion)}
              </div>
            </div>
          </div>
        ))}
    </div>
  );
}

function formatAssertionType(type: string) {
  return (
    (
      {
        status_code: "校验响应状态码",
        jsonpath_equals: "校验 JSON 字段值",
        jsonpath_exists: "校验 JSON 字段存在",
        content_type: "校验响应内容类型",
        header_exists: "校验响应头存在",
        header_equals: "校验响应头值",
        body_not_empty: "校验响应体非空",
        body_sha256: "校验响应体摘要",
      } as Record<string, string>
    )[type] ?? "校验响应结果"
  );
}

function formatAssertionDetail(assertion: Record<string, unknown>) {
  const path = asString(assertion.path);
  const expected = formatUnknown(assertion.expected);
  return path ? `${path} = ${expected}` : expected;
}

function hasValue(value: unknown) {
  return value !== undefined && value !== null && value !== "";
}

function InfoLine({
  className,
  label,
  mono,
  value,
}: {
  className?: string;
  label: string;
  mono?: boolean;
  value: string;
}) {
  return (
    <div className={cn("space-y-1", className)}>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={cn("break-words text-sm", mono ? "font-mono text-xs" : "")}>{value || "-"}</div>
    </div>
  );
}

function KeyValueBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="space-y-1">
      <div className="text-muted-foreground text-xs">{title}</div>
      <JsonBlock value={value} />
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  const upper = method.toUpperCase();
  const tone =
    {
      GET: "border-emerald-200 bg-emerald-50 text-emerald-700",
      POST: "border-sky-200 bg-sky-50 text-sky-700",
      PUT: "border-amber-200 bg-amber-50 text-amber-700",
      PATCH: "border-violet-200 bg-violet-50 text-violet-700",
      DELETE: "border-rose-200 bg-rose-50 text-rose-700",
    }[upper] ?? "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <span
      className={cn(
        "inline-flex h-6 min-w-14 items-center justify-center rounded border px-2 font-semibold text-xs",
        tone,
      )}
    >
      {upper}
    </span>
  );
}

function apiCasePriorityTone(priority: string) {
  const normalized = priority.trim().toUpperCase();
  if (normalized === "P0") return "border-red-200 bg-red-50 text-red-700";
  if (normalized === "P1") return "border-amber-200 bg-amber-50 text-amber-700";
  if (normalized === "P2") return "border-blue-200 bg-blue-50 text-blue-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function formatApiCaseCoverage(coverage: string) {
  const normalized = coverage?.trim().toLowerCase() || "positive";
  return (
    {
      positive: "正向",
      negative: "负向",
      boundary: "边界",
      security: "安全",
      scenario: "场景",
    }[normalized] ?? coverage
  );
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function formatUnknown(value: unknown) {
  if (value === undefined || value === null || value === "") return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
