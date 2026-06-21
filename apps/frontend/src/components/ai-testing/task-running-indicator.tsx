"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Activity, AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { AI_TASK_STARTED_EVENT } from "@/lib/ai-task-events";
import { type ApiTaskItem, apiRequest, formatDateTime } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";

const AGENT_BACKEND_SOURCE_TYPES = new Set([
  "exploration_run",
  "requirement_file",
  "requirement_analysis_run",
  "test_case_generation_run",
]);
const RUNNING_TASK_POLL_INTERVAL_MS = 2_000;
const TASK_START_GRACE_MS = 8_000;

type RunningTaskItem = {
  id: string;
  projectId: string | null;
  projectName: string;
  title: string;
  moduleLabel: string;
  status: string;
  statusLabel: string;
  createdAt: string;
};

function getTaskStatusLabel(task: RunningTaskItem) {
  return task.statusLabel || task.status;
}

function toRunningTask(item: ApiTaskItem): RunningTaskItem {
  return {
    id: item.id,
    projectId: item.project_id,
    projectName: item.project_name,
    title: item.title,
    moduleLabel: item.module_label,
    status: item.status,
    statusLabel: item.status_label,
    createdAt: item.created_at,
  };
}

function isAgentBackendTask(item: ApiTaskItem) {
  return AGENT_BACKEND_SOURCE_TYPES.has(item.source_type);
}

export function TaskRunningIndicator() {
  const { currentProjectId, hasHydrated: hasProjectHydrated, hydrate, scope } = useProjectContextStore();
  const { hasHydrated: hasAuthHydrated, hydrate: hydrateAuth, token } = useAuthStore();
  const [tasks, setTasks] = useState<RunningTaskItem[]>([]);
  const [error, setError] = useState("");
  const [tracking, setTracking] = useState(false);
  const trackingStartedAtRef = useRef(0);
  const loadRequestSeqRef = useRef(0);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  const loadRunningTasks = useCallback(async () => {
    loadRequestSeqRef.current += 1;
    const requestSeq = loadRequestSeqRef.current;
    if (!hasAuthHydrated || !hasProjectHydrated || !token) {
      setTasks([]);
      setError("");
      setTracking(false);
      return;
    }

    try {
      const query =
        scope === "project" && currentProjectId ? `?project_id=${encodeURIComponent(currentProjectId)}` : "";
      const runningTasks = await apiRequest<ApiTaskItem[]>(`/tasks/running${query}`);
      const nextTasks = runningTasks.filter(isAgentBackendTask).map(toRunningTask);
      if (requestSeq !== loadRequestSeqRef.current) {
        return;
      }
      setTasks(nextTasks);
      if (nextTasks.length > 0) {
        setTracking(true);
      } else if (Date.now() - trackingStartedAtRef.current > TASK_START_GRACE_MS) {
        setTracking(false);
      }
      setError("");
    } catch (requestError) {
      if (requestSeq !== loadRequestSeqRef.current) {
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "任务状态加载失败");
      setTasks([]);
      setTracking(true);
    }
  }, [currentProjectId, hasAuthHydrated, hasProjectHydrated, scope, token]);

  useEffect(() => {
    function handleAiTaskStarted() {
      trackingStartedAtRef.current = Date.now();
      setTracking(true);
      void loadRunningTasks();
    }

    window.addEventListener(AI_TASK_STARTED_EVENT, handleAiTaskStarted);
    return () => {
      window.removeEventListener(AI_TASK_STARTED_EVENT, handleAiTaskStarted);
    };
  }, [loadRunningTasks]);

  useEffect(() => {
    if (!hasAuthHydrated || !hasProjectHydrated || !token) {
      return;
    }
    void loadRunningTasks();
  }, [hasAuthHydrated, hasProjectHydrated, loadRunningTasks, token]);

  useEffect(() => {
    if ((!tracking && !error) || !hasAuthHydrated || !hasProjectHydrated || !token) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadRunningTasks();
    }, RUNNING_TASK_POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [error, hasAuthHydrated, hasProjectHydrated, loadRunningTasks, token, tracking]);

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
                    <span>创建于 {formatDateTime(task.createdAt)}</span>
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
