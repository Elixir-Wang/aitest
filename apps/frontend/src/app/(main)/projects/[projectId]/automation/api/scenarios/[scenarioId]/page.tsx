"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function EditApiScenarioPage() {
  const params = useParams<{ projectId: string; scenarioId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "接口自动化", href: `/projects/${params.projectId}/automation/api?tab=scenarios` },
        { label: "编辑场景" },
      ]}
      description="维护场景步骤、变量、校验、发布和运行配置。"
      projectScope="project"
      title="编辑接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} scenarioId={params.scenarioId} />
    </PageShell>
  );
}
