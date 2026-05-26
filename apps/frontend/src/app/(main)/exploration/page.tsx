"use client";

import { useEffect } from "react";

import { ExplorationWorkspace } from "@/components/ai-testing/exploration-workspace";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const hydrate = useProjectContextStore((state) => state.hydrate);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <ExplorationWorkspace
      breadcrumbs={["项目工作区", "探索"]}
      description="查看全部项目的探索任务、页面事实和冲突项。"
      projectId={currentProjectId ?? undefined}
      projectScope="all"
      title="探索"
    />
  );
}
