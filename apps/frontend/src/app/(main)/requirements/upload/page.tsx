"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ai-testing/page-shell";
import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const activeProjects = projects.filter((project) => project.status !== "archived");
  const defaultActiveProjectId = activeProjects.some((project) => project.id === currentProjectId)
    ? (currentProjectId ?? "")
    : (activeProjects[0]?.id ?? "");

  useEffect(() => {
    hydrate();
  }, [hydrate]);

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

  if (activeProjects.length === 0) {
    return (
      <EmptyState
        description="创建或启用项目后，可上传需求文件并生成标准 Markdown 用于分析。"
        status="无可用项目"
        title="暂无可上传项目"
      />
    );
  }

  return (
    <RequirementUploadPage
      backHref="/requirements"
      breadcrumbs={["项目工作区", "需求", "新建"]}
      defaultProjectId={defaultActiveProjectId}
      description="选择关联项目后上传原始需求文件，系统会保存原文档并生成 Markdown 映射。"
      projectScope="all"
      projects={activeProjects}
      title="新建需求"
    />
  );
}
