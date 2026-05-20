"use client";

import { useParams } from "next/navigation";

import { RequirementsPage } from "@/components/ai-testing/requirements-page";
import { projectOptions } from "@/stores/project-context-store";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = projectOptions.find((project) => project.id === projectId)?.name ?? "项目";

  return (
    <RequirementsPage
      breadcrumbs={["项目", projectName, "需求"]}
      description="上传、预览、编辑需求文档，并进行 AI 分析、模块评审和澄清写回。"
      projectId={projectId}
      projectScope="project"
      title="需求"
      uploadHref={`/projects/${projectId}/requirements/upload`}
    />
  );
}
