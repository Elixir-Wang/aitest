"use client";

import { PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { AllPerformanceTestList } from "@/components/ai-testing/performance-testing/all-performance-test-list";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests")}
      description="跨项目查看性能测试任务和最近运行状态。"
      projectScope="all"
      title="性能测试"
    >
      <AllPerformanceTestList />
    </PageShell>
  );
}
