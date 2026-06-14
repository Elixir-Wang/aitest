"use client";

export const AI_TASK_STARTED_EVENT = "ai-task-started";
export const AI_RUNNING_TASKS_CHANGED_EVENT = "ai-running-tasks-changed";

export type AiRunningTasksChangedDetail = {
  tasks: Array<{
    sourceType: string;
    sourceId: string;
    projectId: string | null;
    status: string;
  }>;
};

export function notifyAiTaskStarted() {
  window.dispatchEvent(new Event(AI_TASK_STARTED_EVENT));
}

export function notifyAiRunningTasksChanged(detail: AiRunningTasksChangedDetail) {
  window.dispatchEvent(new CustomEvent<AiRunningTasksChangedDetail>(AI_RUNNING_TASKS_CHANGED_EVENT, { detail }));
}
