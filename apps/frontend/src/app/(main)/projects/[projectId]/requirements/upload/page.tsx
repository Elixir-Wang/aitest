"use client";

import { useParams } from "next/navigation";

import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { projectOptions } from "@/stores/project-context-store";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = projectOptions.find((project) => project.id === projectId)?.name ?? "项目";

  return (
    <RequirementUploadPage
      backHref={`/projects/${projectId}/requirements`}
      breadcrumbs={["项目", projectName, "需求", "上传"]}
      description="上传原始需求文件，系统会保存原文档并生成 Markdown 映射，列表状态先显示为解析中。"
      projectId={projectId}
      projectScope="project"
      title="上传需求"
    />
  );
}
