"use client";

import { useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { RequirementsPage } from "@/components/ai-testing/requirements-page";
import { apiRequest, type ApiProject } from "@/lib/api-client";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [projectName, setProjectName] = useState("项目");

  useEffect(() => {
    let ignore = false;

    async function loadProjectName() {
      try {
        const projects = await apiRequest<ApiProject[]>("/projects");
        const project = projects.find((item) => item.id === projectId);
        if (!ignore) {
          setProjectName(project?.name ?? "项目");
        }
      } catch {
        if (!ignore) {
          setProjectName("项目");
        }
      }
    }

    void loadProjectName();

    return () => {
      ignore = true;
    };
  }, [projectId]);

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
