"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { ScriptReview } from "@/components/ai-testing/performance-testing/script-review";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string; scriptId: string }>();
  const projectName = useProjectName(params.projectId);
  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "性能测试", href: `/projects/${params.projectId}/performance-tests` },
        { label: "任务详情", href: `/projects/${params.projectId}/performance-tests/${params.testId}` },
        { label: "脚本审核" },
      ]}
      description="审核结构化请求配置、校验结果和只读 Locust 脚本。"
      projectScope="project"
      title="Locust 脚本审核"
    >
      <ScriptReview projectId={params.projectId} scriptId={params.scriptId} testId={params.testId} />
    </PageShell>
  );
}
