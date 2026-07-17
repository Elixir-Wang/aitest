"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceRunDetail } from "@/components/ai-testing/performance-testing/performance-run-detail";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string; runId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "performanceTests",
        { label: "任务详情", href: `/projects/${params.projectId}/performance-tests/${params.testId}` },
        { label: "运行详情" },
      )}
      description="实时查看压测指标、失败请求、异常和运行报告。"
      projectScope="project"
      title="性能测试运行"
    >
      <PerformanceRunDetail projectId={params.projectId} runId={params.runId} />
    </PageShell>
  );
}
