"use client";

import { useEffect } from "react";

import { ExplorationRunCreatePage } from "@/components/ai-testing/exploration-run-create-page";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const currentProjectId = useProjectContextStore((state) => state.currentProjectId);
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const scope = useProjectContextStore((state) => state.scope);
  const scopedProjectId = scope === "project" ? currentProjectId : null;

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return <ExplorationRunCreatePage projectId={scopedProjectId ?? undefined} projectScope={scope} />;
}
