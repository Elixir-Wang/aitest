"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestDetail } from "@/components/ai-testing/performance-testing/performance-test-detail";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "性能测试", href: `/projects/${params.projectId}/performance-tests` },
        { label: "任务详情" },
      ]}
      description="查看请求、负载、成功规则和最近运行状态。"
      projectScope="project"
      title="性能测试详情"
    >
      <PerformanceTestDetail projectId={params.projectId} testId={params.testId} />
    </PageShell>
  );
}
