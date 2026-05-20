"use client";

import { RequirementsPage } from "@/components/ai-testing/requirements-page";
import { projectOptions, useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const projectId = currentProjectId ?? projectOptions[0]?.id ?? "zhiliao";
  const projectName = projectOptions.find((project) => project.id === projectId)?.name ?? "当前项目";

  return (
    <RequirementsPage
      breadcrumbs={["项目工作区", "需求"]}
      description={`查看并上传 ${projectName} 的需求文档、评审状态和版本记录。`}
      projectId={projectId}
      projectScope="all"
      title="需求"
      uploadHref="/requirements/upload"
    />
  );
}
