"use client";

import { create } from "zustand";

import { getLocalStorageValue, setLocalStorageValue } from "@/lib/local-storage.client";

const PROJECT_SCOPE_KEY = "ai-testing.project.scope";
const CURRENT_PROJECT_KEY = "ai-testing.project.current";

export type ProjectScope = "all" | "project";

interface ProjectContextState {
  scope: ProjectScope;
  currentProjectId: string | null;
  hasHydrated: boolean;
  hydrate: () => void;
  selectAllProjects: () => void;
  selectProject: (projectId: string) => void;
}

export function getProjectScopedUrl(url: string, projectId: string | null, scope: ProjectScope) {
  if (!url.includes(":projectId")) {
    return url;
  }

  if (scope === "all") {
    return url.replace("/projects/:projectId", "");
  }

  if (!projectId) {
    return "/projects";
  }

  return url.replace(":projectId", projectId);
}

export const useProjectContextStore = create<ProjectContextState>((set) => ({
  scope: "all",
  currentProjectId: null,
  hasHydrated: false,
  hydrate: () => {
    const storedScope = getLocalStorageValue(PROJECT_SCOPE_KEY);
    const storedProjectId = getLocalStorageValue(CURRENT_PROJECT_KEY);

    set({
      scope: storedScope === "project" && storedProjectId ? "project" : "all",
      currentProjectId: storedScope === "project" ? storedProjectId : null,
      hasHydrated: true,
    });
  },
  selectAllProjects: () => {
    setLocalStorageValue(PROJECT_SCOPE_KEY, "all");
    set({ scope: "all", currentProjectId: null, hasHydrated: true });
  },
  selectProject: (projectId) => {
    setLocalStorageValue(PROJECT_SCOPE_KEY, "project");
    setLocalStorageValue(CURRENT_PROJECT_KEY, projectId);
    set({ scope: "project", currentProjectId: projectId, hasHydrated: true });
  },
}));
