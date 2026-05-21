"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ai-testing/page-shell";
import { RequirementsPage } from "@/components/ai-testing/requirements-page";
import { apiRequest, type ApiProject } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const projectId = currentProjectId ?? projects[0]?.id;
  const projectName = projects.find((project) => project.id === projectId)?.name ?? "当前项目";

  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      try {
        const nextProjects = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(nextProjects);
        }
      } catch {
        if (!ignore) {
          setProjects([]);
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, []);

  if (!projectId) {
    return (
      <EmptyState
        description="请先创建项目或在右上角选择一个项目后再管理需求文档。"
        status="无可用项目"
        title="暂无项目"
      />
    );
  }

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
