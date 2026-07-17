"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "新建性能测试" })}
      description="定义接口、请求数据、负载和可选性能目标。"
      projectScope="project"
      title="新建性能测试"
    >
      <PerformanceTestForm initialProjectId={params.projectId} />
    </PageShell>
  );
}
