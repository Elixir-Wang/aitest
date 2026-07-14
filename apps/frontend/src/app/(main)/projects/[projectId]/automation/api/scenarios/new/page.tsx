"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function NewApiScenarioPage() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "接口自动化", href: `/projects/${params.projectId}/automation/api?tab=scenarios` },
        { label: "新建场景" },
      ]}
      description="组合接口用例、配置变量并定义执行顺序。"
      projectScope="project"
      title="新建接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} />
    </PageShell>
  );
}
