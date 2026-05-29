"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Activity, AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { type ApiKnowledgeBuild, type ApiProject, apiRequest, formatDateTime } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";
import {
  createRunningTaskId,
  type RunningTaskItem,
  useRunningTaskStore,
} from "@/stores/running-task-store";

type ExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  status: string;
  updated_at: string;
  started_at?: string | null;
};

const RUNNING_EXPLORATION_STATUSES = new Set(["queued", "running", "waiting_human"]);
const RUNNING_KNOWLEDGE_STATUSES = new Set(["building"]);
const POLL_INTERVAL_MS = 15_000;
const BACKEND_TASK_SOURCE = "backend";

const explorationStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "探索中",
  waiting_human: "等待人工",
};

function getTaskStatusLabel(task: RunningTaskItem) {
  return task.statusLabel || task.status;
}

export function TaskRunningIndicator() {
  const { currentProjectId, hasHydrated: hasProjectHydrated, hydrate, scope } = useProjectContextStore();
  const { hasHydrated: hasAuthHydrated, hydrate: hydrateAuth, token } = useAuthStore();
  const tasks = useRunningTaskStore((state) => state.tasks);
  const replaceTasksBySource = useRunningTaskStore((state) => state.replaceTasksBySource);
  const [error, setError] = useState("");

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  const loadRunningTasks = useCallback(async () => {
    if (!hasAuthHydrated || !hasProjectHydrated || !token) {
      replaceTasksBySource(BACKEND_TASK_SOURCE, []);
      setError("");
      return;
    }

    try {
      const explorationPath =
        scope === "project" && currentProjectId ? `/projects/${currentProjectId}/exploration-runs` : "/exploration-runs";
      const explorations = await apiRequest<ExplorationRun[]>(explorationPath);
      const runningExplorations = explorations
        .filter((item) => RUNNING_EXPLORATION_STATUSES.has(item.status))
        .map<RunningTaskItem>((item) => ({
          id: createRunningTaskId(BACKEND_TASK_SOURCE, `exploration-${item.id}`),
          projectId: item.project_id,
          projectName: item.project_name,
          title: item.title,
          moduleLabel: "站点探索",
          status: item.status,
          statusLabel: explorationStatusLabels[item.status] ?? item.status,
          updatedAt: item.updated_at,
        }));

      const targetProjects =
        scope === "project" && currentProjectId
          ? [{ id: currentProjectId, name: "" }]
          : await apiRequest<ApiProject[]>("/projects").then((projects) => projects.filter((project) => project.status !== "archived"));
      const projectNameById = new Map([
        ...explorations.map((item) => [item.project_id, item.project_name] as const),
        ...targetProjects.map((project) => [project.id, project.name || project.id] as const),
      ]);

      const knowledgeResults = await Promise.allSettled(
        targetProjects.map(async (project) => {
          const builds = await apiRequest<ApiKnowledgeBuild[]>(`/projects/${project.id}/knowledge/builds`);
          return builds
            .filter((item) => RUNNING_KNOWLEDGE_STATUSES.has(item.status))
            .map<RunningTaskItem>((item) => ({
              id: createRunningTaskId(BACKEND_TASK_SOURCE, `knowledge-${item.id}`),
              projectId: item.project_id,
              projectName: projectNameById.get(item.project_id) ?? item.project_id,
              title: item.build_no,
              moduleLabel: "知识库",
              status: item.status,
              statusLabel: item.status_label,
              updatedAt: item.updated_at,
            }));
        }),
      );

      const runningKnowledge = knowledgeResults.flatMap((result) => (result.status === "fulfilled" ? result.value : []));
      replaceTasksBySource(
        BACKEND_TASK_SOURCE,
        [...runningExplorations, ...runningKnowledge].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
      );
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "任务状态加载失败");
      replaceTasksBySource(BACKEND_TASK_SOURCE, []);
    }
  }, [currentProjectId, hasAuthHydrated, hasProjectHydrated, replaceTasksBySource, scope, token]);

  useEffect(() => {
    void loadRunningTasks();
    const timer = window.setInterval(() => {
      void loadRunningTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [loadRunningTasks]);

  const dedupedTasks = useMemo(() => {
    const seen = new Set<string>();
    return tasks.filter((task) => {
      const key = `${task.moduleLabel}:${task.projectId ?? ""}:${task.title}`;
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }, [tasks]);
  const visibleTasks = useMemo(() => dedupedTasks.slice(0, 4), [dedupedTasks]);

  if (dedupedTasks.length === 0 && !error) {
    return null;
  }

  return (
    <HoverCard openDelay={120}>
      <HoverCardTrigger asChild>
        <button
          aria-label="查看执行中任务"
          className={cn(
            "relative inline-flex h-8 items-center gap-2 overflow-hidden rounded-lg border px-2.5 font-medium text-sm transition-colors",
            "border-primary/20 bg-primary/10 text-primary hover:bg-primary/15",
          )}
          type="button"
        >
          <span className="absolute inset-0 bg-gradient-to-r from-primary/10 to-ring/10 opacity-70" />
          <span className="relative flex items-center gap-2">
            {error ? <AlertCircle className="size-4" /> : <Loader2 className="size-4 animate-spin" />}
            <span>{error ? "任务状态异常" : `${dedupedTasks.length} 个任务执行中`}</span>
          </span>
        </button>
      </HoverCardTrigger>
      <HoverCardContent align="center" className="w-80 p-0" sideOffset={10}>
        <div className="relative overflow-hidden rounded-lg border bg-popover">
          <div className="flex items-center gap-3 border-b p-3">
            <span className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Activity className="size-4" />
            </span>
            <div className="min-w-0">
              <div className="font-medium text-sm">{error ? "任务状态同步失败" : "正在执行的任务"}</div>
              <div className="text-muted-foreground text-xs">{error || "后台任务完成后，该提示会自动隐藏。"}</div>
            </div>
          </div>
          {error ? null : (
            <div className="space-y-2 p-3">
              {visibleTasks.map((task) => (
                <div className="rounded-md border bg-background/60 p-2.5" key={task.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-sm">{task.title}</div>
                    </div>
                    <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-primary text-xs">
                      {getTaskStatusLabel(task)}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-muted-foreground text-xs">
                    <Clock3 className="size-3.5" />
                    <span>更新于 {formatDateTime(task.updatedAt)}</span>
                  </div>
                </div>
              ))}
              {dedupedTasks.length > visibleTasks.length ? (
                <div className="flex items-center gap-2 text-muted-foreground text-xs">
                  <CheckCircle2 className="size-3.5" />
                  <span>另有 {dedupedTasks.length - visibleTasks.length} 个任务正在执行</span>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
