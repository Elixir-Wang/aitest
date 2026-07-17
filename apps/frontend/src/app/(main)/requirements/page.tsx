"use client";

import { useEffect } from "react";

import { EmptyState } from "@/components/ai-testing/page-shell";
import { RequirementsPage } from "@/components/ai-testing/requirements-page";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const scope = useProjectContextStore((state) => state.scope);
  const scopedProjectId = scope === "project" ? currentProjectId : null;

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  if (scope === "project" && !scopedProjectId) {
    return (
      <EmptyState
        description="在顶部项目切换器中选择具体项目后，可查看该项目的需求文档。"
        status="未选择项目"
        title="请选择项目"
      />
    );
  }

  return (
    <RequirementsPage
      breadcrumbs={moduleBreadcrumbs("requirements")}
      description={
        scope === "all"
          ? "查看全部项目的需求文档、评审状态和版本记录。"
          : "查看并上传当前项目的需求文档、评审状态和版本记录。"
      }
      projectId={scopedProjectId ?? undefined}
      projectScope={scope}
      title="需求"
      uploadHref="/requirements/upload"
    />
  );
}
