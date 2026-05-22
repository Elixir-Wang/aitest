"use client";

import { useEffect, useState } from "react";

import { apiRequest, type ApiProject } from "@/lib/api-client";

export function useProjectName(projectId: string | undefined, fallback = "项目") {
  const [projectName, setProjectName] = useState(fallback);

  useEffect(() => {
    if (!projectId) {
      setProjectName(fallback);
      return;
    }

    let ignore = false;

    async function loadProjectName() {
      try {
        const projects = await apiRequest<ApiProject[]>("/projects");
        const project = projects.find((item) => item.id === projectId);
        if (!ignore) {
          setProjectName(project?.name ?? fallback);
        }
      } catch {
        if (!ignore) {
          setProjectName(fallback);
        }
      }
    }

    void loadProjectName();

    return () => {
      ignore = true;
    };
  }, [fallback, projectId]);

  return projectName;
}
