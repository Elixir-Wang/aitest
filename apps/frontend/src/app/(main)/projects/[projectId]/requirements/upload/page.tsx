"use client";

import { useParams } from "next/navigation";

import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = useProjectName(projectId);

  return (
    <RequirementUploadPage
      backHref={`/projects/${projectId}/requirements`}
      breadcrumbs={["项目", projectName, "需求", "上传"]}
      description="上传原始需求文件，系统会保存原文档并生成 Markdown 映射，列表状态先显示为解析中。"
      defaultProjectId={projectId}
      projectScope="project"
      projects={[{ id: projectId, name: projectName, description: "", status: "active", created_at: "", updated_at: "", available_actions: [] }]}
      title="上传需求"
    />
  );
}
