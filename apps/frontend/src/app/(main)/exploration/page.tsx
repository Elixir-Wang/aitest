"use client";

import { useEffect } from "react";

import { ExplorationWorkspace } from "@/components/ai-testing/exploration-workspace";
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

  return (
    <ExplorationWorkspace
      breadcrumbs={moduleBreadcrumbs("exploration")}
      description="查看全部项目的探索任务、页面事实和冲突项。"
      projectId={scopedProjectId ?? undefined}
      projectScope={scope}
      title="探索"
    />
  );
}
