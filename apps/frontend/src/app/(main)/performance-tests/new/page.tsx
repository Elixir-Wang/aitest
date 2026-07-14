"use client";

import { useSearchParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";

export default function Page() {
  const searchParams = useSearchParams();

  return (
    <PageShell
      breadcrumbs={[{ label: "测试资产" }, { label: "性能测试", href: "/performance-tests" }, { label: "新建" }]}
      description="选择项目、环境和接口，配置请求数据与 Locust 负载模式。"
      projectScope="all"
      title="新建性能测试"
    >
      <PerformanceTestForm initialProjectId={searchParams.get("projectId") ?? ""} />
    </PageShell>
  );
}
