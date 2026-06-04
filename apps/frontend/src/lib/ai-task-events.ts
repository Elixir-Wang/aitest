"use client";

export const AI_TASK_STARTED_EVENT = "ai-task-started";

export function notifyAiTaskStarted() {
  window.dispatchEvent(new Event(AI_TASK_STARTED_EVENT));
}
