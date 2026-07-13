"use client";

import { PageShell } from "@/components/ai-testing/page-shell";
import { AllPerformanceTestList } from "@/components/ai-testing/performance-testing/all-performance-test-list";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={[{ label: "测试资产" }, { label: "性能测试" }]}
      description="跨项目查看性能测试任务和最近运行状态。"
      projectScope="all"
      title="性能测试"
    >
      <AllPerformanceTestList />
    </PageShell>
  );
}
