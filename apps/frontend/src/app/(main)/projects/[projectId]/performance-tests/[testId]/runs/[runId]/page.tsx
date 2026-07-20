"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceRunDetail } from "@/components/ai-testing/performance-testing/performance-run-detail";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string; runId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "Locust 控制台" })}
      description="项目内迁移的 Locust 原生启动、统计、图表、失败、异常和下载控制台。"
      projectScope="project"
      title="Locust 控制台"
    >
      <PerformanceRunDetail projectId={params.projectId} runId={params.runId} testId={params.testId} />
    </PageShell>
  );
}
