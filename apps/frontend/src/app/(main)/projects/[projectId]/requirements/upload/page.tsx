"use client";

import { useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { EmptyState } from "@/components/ai-testing/page-shell";
import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { type ApiProject, apiRequest } from "@/lib/api-client";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = useProjectName(projectId);
  const [project, setProject] = useState<ApiProject | null>(null);
  const [loadingProject, setLoadingProject] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadProject() {
      setLoadingProject(true);
      try {
        const projects = await apiRequest<ApiProject[]>("/projects");
        const nextProject = projects.find((item) => item.id === projectId) ?? null;
        if (!ignore) {
          setProject(nextProject);
        }
      } catch {
        if (!ignore) {
          setProject(null);
        }
      } finally {
        if (!ignore) {
          setLoadingProject(false);
        }
      }
    }

    void loadProject();

    return () => {
      ignore = true;
    };
  }, [projectId]);

  if (loadingProject) {
    return <EmptyState description="正在确认项目状态。" status="加载中" title="上传需求" />;
  }

  if (!project || project.status === "archived") {
    return (
      <EmptyState
        description="归档项目仅支持查看历史资料，不能继续上传需求。请恢复项目后再上传。"
        status={project?.status === "archived" ? "项目已归档" : "项目不可用"}
        title="不能上传需求"
      />
    );
  }

  return (
    <RequirementUploadPage
      backHref={`/projects/${projectId}/requirements`}
      breadcrumbs={["项目", projectName, "需求", "上传"]}
      description="上传原始需求文件，系统会保存原文档并生成 Markdown 映射，列表状态先显示为解析中。"
      defaultProjectId={projectId}
      projectScope="project"
      projects={[project]}
      title="上传需求"
    />
  );
}
