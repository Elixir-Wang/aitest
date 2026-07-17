"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestList } from "@/components/ai-testing/performance-testing/performance-test-list";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests")}
      description="配置单接口负载、查看 Locust 运行和性能目标结果。"
      projectScope="project"
      title="性能测试"
    >
      <PerformanceTestList projectId={params.projectId} />
    </PageShell>
  );
}
