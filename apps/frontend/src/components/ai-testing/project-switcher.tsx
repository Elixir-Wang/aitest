"use client";

import { useEffect } from "react";

import { FolderKanban } from "lucide-react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { projectOptions, useProjectContextStore } from "@/stores/project-context-store";

const ALL_PROJECTS_VALUE = "all";
const ALL_PROJECTS_LABEL = "全部项目";

export function ProjectSwitcher({ scope: _scope }: { scope: "all" | "project" }) {
  const { currentProjectId, hydrate, scope: currentScope, selectAllProjects, selectProject } = useProjectContextStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const selected = currentScope === "all" ? ALL_PROJECTS_VALUE : (currentProjectId ?? ALL_PROJECTS_VALUE);
  const selectedProject = projectOptions.find((item) => item.id === selected);
  const longestLabel = [ALL_PROJECTS_LABEL, ...projectOptions.map((project) => project.name)].reduce((longest, label) =>
    label.length > longest.length ? label : longest,
  );

  return (
    <div className="relative inline-grid max-w-72 grid-cols-[max-content]">
      <span aria-hidden="true" className="invisible col-start-1 row-start-1 flex h-8 items-center gap-2 whitespace-nowrap rounded-lg border px-2.5 text-sm">
        <FolderKanban className="size-4" />
        {longestLabel}
        <span className="size-4" />
      </span>
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
        <SelectTrigger aria-label="切换项目" className="col-start-1 row-start-1 w-full min-w-0 gap-2">
          <FolderKanban className="size-4 text-muted-foreground" />
          <SelectValue placeholder="选择项目" />
        </SelectTrigger>
        <SelectContent align="end" className="min-w-(--radix-select-trigger-width)" position="popper">
          <SelectItem value={ALL_PROJECTS_VALUE}>{ALL_PROJECTS_LABEL}</SelectItem>
          {projectOptions.map((project) => (
            <SelectItem key={project.id} value={project.id}>
              {project.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
