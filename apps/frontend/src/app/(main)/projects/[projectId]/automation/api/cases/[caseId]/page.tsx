"use client";

import { type ReactNode, useEffect, useState } from "react";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type ApiAutomationTestCase, formatDateTime, getApiAutomationTestCase } from "@/lib/api-client";
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
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild variant="outline">
            <Link href={`/projects/${projectId}/automation/api`}>
              <ArrowLeft className="size-4" />
              返回列表
            </Link>
          </Button>
          <Button disabled={loading} onClick={() => window.location.reload()} variant="outline">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            刷新
          </Button>
        </div>
      }
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
            <div className="flex flex-col gap-2 border-b pb-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge className={cn("border", apiCasePriorityTone(testCase.priority))} variant="outline">
                  {testCase.priority || "P2"}
                </Badge>
                <Badge variant="outline">{testCase.coverage || "positive"}</Badge>
              </div>
              <h1 className="font-semibold text-xl">{testCase.title}</h1>
            </div>
            <div className="grid gap-4 xl:grid-cols-2">
              <ReviewBlock title="基础信息">{renderApiCaseBasicInfo(testCase)}</ReviewBlock>
              <ReviewBlock title="前置条件">{renderApiCasePreconditions(testCase.preconditions)}</ReviewBlock>
              <ReviewBlock title="请求信息">{renderApiCaseRequest(testCase.request)}</ReviewBlock>
              <ReviewBlock title="测试数据">{renderApiCaseTestData(testCase.test_data)}</ReviewBlock>
              <ReviewBlock title="预期结果">{renderApiCaseExpected(testCase.expected)}</ReviewBlock>
              <ReviewBlock title="断言">{renderApiCaseAssertions(testCase.assertions)}</ReviewBlock>
            </div>
          </>
        ) : (
          <div className="flex min-h-52 items-center justify-center text-muted-foreground text-sm">接口用例不存在</div>
        )}
      </ShellSection>
    </PageShell>
  );
}

function ReviewBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border bg-white p-4">
      <h3 className="mb-3 font-medium text-[#101828] text-sm">{title}</h3>
      <div className="whitespace-pre-wrap text-[#101828] text-sm leading-6">{children}</div>
    </section>
  );
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md bg-[#F7F8FA] p-3 font-mono text-[#101828] text-xs">
      {JSON.stringify(value ?? {}, null, 2)}
    </pre>
  );
}

function renderApiCaseBasicInfo(testCase: ApiAutomationTestCase) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <InfoLine label="标题" value={testCase.title} />
      <InfoLine label="优先级" value={testCase.priority || "P2"} />
      <InfoLine label="覆盖类型" value={testCase.coverage || "positive"} />
      <InfoLine label="来源" value={testCase.source || "ai_generated"} />
      <InfoLine label="更新时间" value={formatDateTime(testCase.updated_at)} />
      <div className="space-y-1 sm:col-span-2">
        <div className="text-muted-foreground text-xs">标签</div>
        <div className="flex flex-wrap gap-1.5">
          {testCase.tags.length > 0 ? (
            testCase.tags.map((tag) => (
              <Badge className="rounded-md" key={tag} variant="outline">
                {tag}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground text-sm">无标签</span>
          )}
        </div>
      </div>
      {testCase.notes ? <InfoLine className="sm:col-span-2" label="备注" value={testCase.notes} /> : null}
    </div>
  );
}

function renderApiCasePreconditions(preconditions: string[]) {
  if (preconditions.length === 0) {
    return <div className="text-muted-foreground text-sm">无额外前置条件</div>;
  }
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
        <code className="rounded bg-[#F7F8FA] px-2 py-1 text-xs">{path}</code>
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
          <div className="rounded-md border bg-[#FCFCFD] p-3" key={name}>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="font-medium text-sm">{name}</div>
            </div>
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <InfoLine label="值" mono value={formatUnknown(item.value)} />
              <InfoLine label="来源" value={asString(item.source) || "-"} />
              <InfoLine label="必填" value={item.required === true ? "是" : "否"} />
              <InfoLine label="敏感" value={item.sensitive === true ? "是" : "否"} />
            </div>
            {asString(item.note) ? <div className="mt-2 text-muted-foreground text-sm">{asString(item.note)}</div> : null}
          </div>
        );
      })}
    </div>
  );
}

function renderApiCaseExpected(expected: Record<string, unknown>) {
  const statusCode = expected.status_code;
  const businessResult = asString(expected.business_result);
  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {statusCode !== undefined ? <InfoLine label="状态码" value={String(statusCode)} /> : null}
        {businessResult ? <InfoLine label="业务结果" value={businessResult} /> : null}
      </div>
      <JsonBlock value={expected} />
    </div>
  );
}

function renderApiCaseAssertions(assertions: Record<string, unknown>[]) {
  if (assertions.length === 0) {
    return <div className="text-muted-foreground text-sm">暂无断言</div>;
  }
  return (
    <div className="space-y-3">
      {assertions.map((assertion) => (
        <div className="grid gap-2 rounded-md border bg-[#FCFCFD] p-3 sm:grid-cols-3" key={JSON.stringify(assertion)}>
          <InfoLine label="类型" value={asString(assertion.type) || "-"} />
          <InfoLine label="路径" value={asString(assertion.path) || "-"} />
          <InfoLine label="期望值" mono value={formatUnknown(assertion.expected)} />
        </div>
      ))}
    </div>
  );
}

function InfoLine({ className, label, mono, value }: { className?: string; label: string; mono?: boolean; value: string }) {
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

  return <span className={cn("inline-flex h-6 min-w-14 items-center justify-center rounded border px-2 font-semibold text-xs", tone)}>{upper}</span>;
}

function apiCasePriorityTone(priority: string) {
  const normalized = priority.trim().toUpperCase();
  if (normalized === "P0") return "border-red-200 bg-red-50 text-red-700";
  if (normalized === "P1") return "border-amber-200 bg-amber-50 text-amber-700";
  if (normalized === "P2") return "border-blue-200 bg-blue-50 text-blue-700";
  return "border-slate-200 bg-slate-50 text-slate-700";
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
