"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import { ArrowLeft, ClipboardCheck, Loader2 } from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiManualTestCase, apiRequest, formatDateTime } from "@/lib/api-client";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function ManualTestCaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const searchParams = useSearchParams();
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const queryProjectId = searchParams.get("project") ?? "";
  const projectId = queryProjectId || (projectScope === "project" ? (currentProjectId ?? "") : "");
  const [testCase, setTestCase] = useState<ApiManualTestCase | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasHydrated) {
      hydrate();
    }
  }, [hasHydrated, hydrate]);

  const loadDetail = useCallback(async () => {
    if (!projectId || !params.caseId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const detail = await apiRequest<ApiManualTestCase>(`/projects/${projectId}/test-cases/${params.caseId}`);
      setTestCase(detail);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例信息加载失败");
    } finally {
      setLoading(false);
    }
  }, [params.caseId, projectId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const detailSteps =
    testCase?.steps.map((step, index) => ({
      ...step,
      rowKey: `${testCase.id}-step-${index}`,
    })) ?? [];

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("testCases", { label: "用例信息" })}
      description="查看手动测试用例的前置条件、操作步骤和预期结果。"
      projectScope={projectScope}
      title="用例信息"
    >
      {loading ? (
        <ShellSection>
          <div className="flex min-h-48 items-center justify-center text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            用例信息加载中
          </div>
        </ShellSection>
      ) : testCase ? (
        <ShellSection>
          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <div className="rounded-lg border bg-muted/40 p-2">
                  <ClipboardCheck className="size-5 text-primary" />
                </div>
                <div>
                  <h1 className="font-semibold text-xl tracking-tight">{testCase.title}</h1>
                </div>
              </div>
              <Button asChild variant="outline">
                <Link href="/test-cases">
                  <ArrowLeft className="size-4" />
                  返回测试用例
                </Link>
              </Button>
            </div>

            <div className="grid gap-3 text-sm sm:grid-cols-3">
              <div className="rounded-lg border bg-card p-4">
                <div className="text-muted-foreground">所属项目</div>
                <div className="mt-1 font-medium">{testCase.project_name}</div>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <div className="text-muted-foreground">创建时间</div>
                <div className="mt-1 font-medium">{formatDateTime(testCase.created_at)}</div>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <div className="text-muted-foreground">更新时间</div>
                <div className="mt-1 font-medium">{formatDateTime(testCase.updated_at)}</div>
              </div>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>用例信息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <section>
                  <h2 className="font-medium text-sm">前置条件</h2>
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground text-sm">
                    {testCase.preconditions || "未填写"}
                  </p>
                </section>

                <section>
                  <h2 className="font-medium text-sm">操作步骤</h2>
                  <div className="mt-2 overflow-hidden rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-20">序号</TableHead>
                          <TableHead>操作步骤</TableHead>
                          <TableHead>预期结果</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailSteps.length > 0 ? (
                          detailSteps.map((step, index) => (
                            <TableRow key={step.rowKey}>
                              <TableCell>{index + 1}</TableCell>
                              <TableCell className="whitespace-pre-wrap align-top">{step.action}</TableCell>
                              <TableCell className="whitespace-pre-wrap align-top">{step.expected_result}</TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell className="text-muted-foreground" colSpan={3}>
                              未填写操作步骤
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </section>

                <section>
                  <h2 className="font-medium text-sm">备注</h2>
                  <p className="mt-2 whitespace-pre-wrap text-muted-foreground text-sm">{testCase.notes || "未填写"}</p>
                </section>
              </CardContent>
            </Card>
          </div>
        </ShellSection>
      ) : (
        <ShellSection>
          <div className="flex min-h-48 items-center justify-center text-muted-foreground">未找到该测试用例</div>
        </ShellSection>
      )}
    </PageShell>
  );
}
