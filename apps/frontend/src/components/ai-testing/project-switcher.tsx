"use client";

import { useEffect, useState } from "react";

import { FolderKanban } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

const ALL_PROJECTS_VALUE = "all";
const ALL_PROJECTS_LABEL = "全部项目";
const PROJECT_LIST_CHANGED_EVENT = "ai-testing:project-list-changed";

export function ProjectSwitcher({ scope: _scope }: { scope: "all" | "project" }) {
  const { currentProjectId, hydrate, scope: currentScope, selectAllProjects, selectProject } = useProjectContextStore();
  const [projectOptions, setProjectOptions] = useState<ApiProject[]>([]);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const selected = currentScope === "all" ? ALL_PROJECTS_VALUE : (currentProjectId ?? ALL_PROJECTS_VALUE);
  const selectedProject = projectOptions.find((item) => item.id === selected);

  useEffect(() => {
    async function loadProjects() {
      try {
        const projects = await apiRequest<ApiProject[]>("/projects");
        setProjectOptions(projects);
      } catch {
        setProjectOptions([]);
      }
    }

    void loadProjects();

    function handleProjectListChanged() {
      void loadProjects();
    }

    window.addEventListener(PROJECT_LIST_CHANGED_EVENT, handleProjectListChanged);
    return () => {
      window.removeEventListener(PROJECT_LIST_CHANGED_EVENT, handleProjectListChanged);
    };
  }, []);

  return (
    <div className="relative inline-grid max-w-72 grid-cols-[max-content] justify-items-center">
      <Select
        onValueChange={(nextValue) => {
          if (nextValue === ALL_PROJECTS_VALUE) {
            selectAllProjects();
            return;
          }

          selectProject(nextValue);
        }}
        value={selectedProject?.id ?? ALL_PROJECTS_VALUE}
      >
        <SelectTrigger aria-label="切换项目" className="w-fit min-w-0 gap-2 justify-self-center">
          <FolderKanban className="size-4 text-muted-foreground" />
          <SelectValue placeholder="选择项目" />
        </SelectTrigger>
        <SelectContent
          align="center"
          className="w-max min-w-(--radix-select-trigger-width)"
          position="popper"
          viewportClassName="w-max"
        >
          <SelectItem value={ALL_PROJECTS_VALUE} className="whitespace-nowrap">
            {ALL_PROJECTS_LABEL}
          </SelectItem>
          {projectOptions.map((project) => (
            <SelectItem key={project.id} value={project.id} className="whitespace-nowrap">
              {project.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
