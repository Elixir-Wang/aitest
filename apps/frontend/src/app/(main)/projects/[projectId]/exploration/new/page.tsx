"use client";

import { useParams } from "next/navigation";

import { ExplorationRunCreatePage } from "@/components/ai-testing/exploration-run-create-page";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <ExplorationRunCreatePage
      projectId={params.projectId}
      projectName={projectName}
      projectScope="project"
    />
  );
}
