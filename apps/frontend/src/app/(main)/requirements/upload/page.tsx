"use client";

import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { projectOptions, useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const projectId = currentProjectId ?? projectOptions[0]?.id ?? "zhiliao";
  const projectName = projectOptions.find((project) => project.id === projectId)?.name ?? "当前项目";

  return (
    <RequirementUploadPage
      backHref="/requirements"
      breadcrumbs={["项目工作区", "需求", "上传"]}
      description={`上传 ${projectName} 的原始需求文件，系统会保存原文档并生成 Markdown 映射。`}
      projectId={projectId}
      projectScope="all"
      title="上传需求"
    />
  );
}
