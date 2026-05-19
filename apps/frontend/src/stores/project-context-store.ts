"use client";

import { create } from "zustand";

import { getLocalStorageValue, setLocalStorageValue } from "@/lib/local-storage.client";

const PROJECT_SCOPE_KEY = "ai-testing.project.scope";
const CURRENT_PROJECT_KEY = "ai-testing.project.current";

export type ProjectScope = "all" | "project";

export interface ProjectOption {
  id: string;
  name: string;
  helper: string;
  status: "active" | "archived";
}

export const projectOptions: ProjectOption[] = [
  { id: "zhiliao", name: "知了平台", helper: "核心业务项目", status: "active" },
  { id: "hawk", name: "鹰眼平台", helper: "示例项目", status: "active" },
];

interface ProjectContextState {
  scope: ProjectScope;
  currentProjectId: string | null;
  hasHydrated: boolean;
  hydrate: () => void;
  selectAllProjects: () => void;
  selectProject: (projectId: string) => void;
}

export function getProjectScopedUrl(url: string, projectId: string | null) {
  if (!url.includes(":projectId")) {
    return url;
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
    const safeProjectId = projectOptions.some((item) => item.id === storedProjectId) ? storedProjectId : null;

    set({
      scope: storedScope === "project" && safeProjectId ? "project" : "all",
      currentProjectId: storedScope === "project" ? safeProjectId : null,
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
