"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestDetail } from "@/components/ai-testing/performance-testing/performance-test-detail";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "任务详情" })}
      description="查看请求、负载、成功规则和最近运行状态。"
      projectScope="project"
      title="性能测试详情"
    >
      <PerformanceTestDetail projectId={params.projectId} testId={params.testId} />
    </PageShell>
  );
}
