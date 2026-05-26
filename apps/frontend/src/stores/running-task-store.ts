"use client";

import { create } from "zustand";

export type RunningTaskItem = {
  id: string;
  projectId: string | null;
  projectName: string;
  title: string;
  moduleLabel: string;
  status: string;
  statusLabel: string;
  updatedAt: string;
};

interface RunningTaskState {
  tasks: RunningTaskItem[];
  upsertTask: (task: RunningTaskItem) => void;
  removeTask: (taskId: string) => void;
  replaceTasksBySource: (source: string, tasks: RunningTaskItem[]) => void;
}

function sourcePrefix(source: string) {
  return `${source}:`;
}

export const useRunningTaskStore = create<RunningTaskState>((set) => ({
  tasks: [],
  upsertTask: (task) =>
    set((state) => ({
      tasks: [task, ...state.tasks.filter((item) => item.id !== task.id)],
    })),
  removeTask: (taskId) =>
    set((state) => ({
      tasks: state.tasks.filter((item) => item.id !== taskId),
    })),
  replaceTasksBySource: (source, tasks) =>
    set((state) => ({
      tasks: [...tasks, ...state.tasks.filter((item) => !item.id.startsWith(sourcePrefix(source)))],
    })),
}));

export function createRunningTaskId(source: string, id: string) {
  return `${sourcePrefix(source)}${id}`;
}
