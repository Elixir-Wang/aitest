"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";
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
        { label: "性能测试", href: `/projects/${params.projectId}/performance-tests` },
        { label: "新建" },
      ]}
      description="定义接口、请求数据、负载和可选性能目标。"
      projectScope="project"
      title="新建性能测试"
    >
      <PerformanceTestForm initialProjectId={params.projectId} />
    </PageShell>
  );
}
