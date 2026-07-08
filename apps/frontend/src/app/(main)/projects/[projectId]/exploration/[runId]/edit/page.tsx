"use client";

import { useParams } from "next/navigation";

import { ExplorationRunCreatePage } from "@/components/ai-testing/exploration-run-create-page";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string; runId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <ExplorationRunCreatePage
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "探索", href: "/exploration" },
        { label: "编辑探索任务" },
      ]}
      mode="edit"
      projectId={params.projectId}
      projectName={projectName}
      projectScope="project"
      runId={params.runId}
    />
  );
}
