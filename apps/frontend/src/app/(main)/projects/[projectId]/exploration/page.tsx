"use client";

import { useParams } from "next/navigation";

import { ExplorationWorkspace } from "@/components/ai-testing/exploration-workspace";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <ExplorationWorkspace
      breadcrumbs={["项目", projectName, "探索"]}
      description="配置站点探索任务，沉淀页面事实、探索文档、候选需求和冲突项。"
      projectId={params.projectId}
      projectName={projectName}
      projectScope="project"
      title="探索"
    />
  );
}
