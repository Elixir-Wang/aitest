"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestList } from "@/components/ai-testing/performance-testing/performance-test-list";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "性能测试" },
      ]}
      description="配置单接口负载、查看 Locust 运行和性能目标结果。"
      projectScope="project"
      title="性能测试"
    >
      <PerformanceTestList projectId={params.projectId} />
    </PageShell>
  );
}
