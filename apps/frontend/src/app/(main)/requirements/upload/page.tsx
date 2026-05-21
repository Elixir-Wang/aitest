"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/ai-testing/page-shell";
import { RequirementUploadPage } from "@/components/ai-testing/requirement-upload-page";
import { apiRequest, type ApiProject } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const [projects, setProjects] = useState<ApiProject[]>([]);

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

  if (projects.length === 0) {
    return (
      <EmptyState
        description="请先创建项目或在右上角选择一个项目后再上传需求文档。"
        status="无可用项目"
        title="暂无项目"
      />
    );
  }

  return (
    <RequirementUploadPage
      backHref="/requirements"
      breadcrumbs={["项目工作区", "需求", "上传"]}
      defaultProjectId={currentProjectId ?? projects[0]?.id ?? ""}
      description="选择关联项目后上传原始需求文件，系统会保存原文档并生成 Markdown 映射。"
      projectScope="all"
      projects={projects}
      title="上传需求"
    />
  );
}
