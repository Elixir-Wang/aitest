"use client";

import { useMemo, useState } from "react";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AgentPlanStatus = "pending" | "queued" | "in-progress" | "running" | "completed" | "partial" | "blocked" | "failed";

export type AgentPlanSubtask = {
  id: string;
  title: string;
  description?: string;
  status: AgentPlanStatus;
  meta?: string[];
};

export type AgentPlanTask = {
  id: string;
  title: string;
  description?: string;
  status: AgentPlanStatus;
  priority?: string;
  dependencies?: string[];
  subtasks?: AgentPlanSubtask[];
  meta?: string[];
};

type AgentPlanProps = {
  tasks: AgentPlanTask[];
  defaultExpandedTaskIds?: string[];
  emptyLabel?: string;
  className?: string;
};

const statusLabels: Record<AgentPlanStatus, string> = {
  pending: "待探索",
  queued: "排队中",
  "in-progress": "探索中",
  running: "探索中",
  completed: "已完成",
  partial: "部分完成",
  blocked: "阻塞",
  failed: "失败",
};

const statusStyles: Record<AgentPlanStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  queued: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  "in-progress": "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  partial: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  blocked: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

function normalizeStatus(status: string): AgentPlanStatus {
  if (status === "waiting_human") {
    return "blocked";
  }
  if (status === "running") {
    return "in-progress";
  }
  if (status in statusLabels) {
    return status as AgentPlanStatus;
  }
  return "pending";
}

function StatusIcon({ status, subtask = false }: { status: AgentPlanStatus | string; subtask?: boolean }) {
  const normalized = normalizeStatus(status);
  const className = subtask ? "size-3.5" : "size-4";
  if (normalized === "completed") {
    return <CheckCircle2 className={cn(className, "text-green-500")} />;
  }
  if (normalized === "in-progress" || normalized === "running" || normalized === "queued") {
    return (
      <motion.span
        animate={{ rotate: 360 }}
        className="block"
        transition={{ duration: 1.1, ease: "linear", repeat: Infinity }}
      >
        <CircleDotDashed className={cn(className, "text-blue-500")} />
      </motion.span>
    );
  }
  if (normalized === "partial") {
    return <CircleAlert className={cn(className, "text-amber-500")} />;
  }
  if (normalized === "blocked" || normalized === "failed") {
    return <CircleX className={cn(className, "text-red-500")} />;
  }
  return <Circle className={cn(className, "text-muted-foreground")} />;
}

export function AgentPlan({ tasks, defaultExpandedTaskIds, emptyLabel = "暂无探索模块", className }: AgentPlanProps) {
  const initialExpanded = useMemo(() => {
    if (defaultExpandedTaskIds?.length) {
      return defaultExpandedTaskIds;
    }
    return tasks.slice(0, 1).map((task) => task.id);
  }, [defaultExpandedTaskIds, tasks]);
  const [expandedTasks, setExpandedTasks] = useState<string[]>(initialExpanded);
  const [expandedSubtasks, setExpandedSubtasks] = useState<Record<string, boolean>>({});

  function toggleTaskExpansion(taskId: string) {
    setExpandedTasks((current) =>
      current.includes(taskId) ? current.filter((id) => id !== taskId) : [...current, taskId],
    );
  }

  function toggleSubtaskExpansion(taskId: string, subtaskId: string) {
    const key = `${taskId}-${subtaskId}`;
    setExpandedSubtasks((current) => ({ ...current, [key]: !current[key] }));
  }

  if (tasks.length === 0) {
    return <div className={cn("rounded-lg border bg-card p-6 text-center text-muted-foreground text-sm", className)}>{emptyLabel}</div>;
  }

  return (
    <div className={cn("w-full min-w-0 max-w-full overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm", className)}>
      <LayoutGroup>
        <div className="p-3">
          <ul className="space-y-1 overflow-hidden">
            {tasks.map((task, index) => {
              const taskStatus = normalizeStatus(task.status);
              const isExpanded = expandedTasks.includes(task.id);
              return (
                <motion.li
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(index !== 0 && "mt-1 pt-2")}
                  initial={{ opacity: 0, y: -5 }}
                  key={task.id}
                  transition={{ duration: 0.18 }}
                >
                  <motion.div
                    className="group flex min-w-0 items-center rounded-md px-3 py-2"
                    whileHover={{ backgroundColor: "hsl(var(--muted) / 0.55)" }}
                  >
                    <div className="mr-2 flex-shrink-0">
                      <AnimatePresence mode="wait">
                        <motion.div
                          animate={{ opacity: 1, scale: 1, rotate: 0 }}
                          exit={{ opacity: 0, scale: 0.85, rotate: 10 }}
                          initial={{ opacity: 0, scale: 0.85, rotate: -10 }}
                          key={taskStatus}
                          transition={{ duration: 0.16 }}
                        >
                          <StatusIcon status={taskStatus} />
                        </motion.div>
                      </AnimatePresence>
                    </div>

                    <button
                      className="flex min-w-0 flex-1 cursor-pointer items-center justify-between gap-3 text-left"
                      onClick={() => toggleTaskExpansion(task.id)}
                      type="button"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-sm">{task.title}</div>
                        {task.description ? <div className="truncate text-muted-foreground text-xs">{task.description}</div> : null}
                      </div>
                      <div className="flex flex-shrink-0 flex-wrap items-center justify-end gap-2">
                        {task.dependencies?.map((dependency) => (
                          <Badge className="h-5 px-1.5 text-[10px]" key={dependency} variant="secondary">
                            {dependency}
                          </Badge>
                        ))}
                        <span className={cn("rounded px-1.5 py-0.5 text-xs", statusStyles[taskStatus])}>
                          {statusLabels[taskStatus]}
                        </span>
                      </div>
                    </button>
                  </motion.div>

                  <AnimatePresence>
                    {isExpanded && task.subtasks?.length ? (
                      <motion.div
                        animate={{ height: "auto", opacity: 1 }}
                        className="relative overflow-hidden"
                        exit={{ height: 0, opacity: 0 }}
                        initial={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: [0.2, 0.65, 0.3, 0.9] }}
                      >
                        <div className="absolute top-0 bottom-0 left-[20px] border-muted-foreground/30 border-l border-dashed" />
                        <ul className="mt-1 mr-2 mb-1.5 ml-3 space-y-0.5">
                          {task.subtasks.map((subtask) => {
                            const subtaskStatus = normalizeStatus(subtask.status);
                            const subtaskKey = `${task.id}-${subtask.id}`;
                            const isSubtaskExpanded = expandedSubtasks[subtaskKey];
                            return (
                              <motion.li
                                animate={{ opacity: 1, x: 0 }}
                                className="flex min-w-0 flex-col py-0.5 pl-6"
                                initial={{ opacity: 0, x: -8 }}
                                key={subtask.id}
                                transition={{ duration: 0.16 }}
                              >
                                <button
                                  className="flex min-w-0 flex-1 items-center rounded-md p-1 text-left"
                                  onClick={() => toggleSubtaskExpansion(task.id, subtask.id)}
                                  type="button"
                                >
                                  <span className="mr-2 flex-shrink-0">
                                    <StatusIcon status={subtaskStatus} subtask />
                                  </span>
                                  <span className="min-w-0 flex-1 truncate text-sm">
                                    {subtask.title}
                                  </span>
                                  <span
                                    className={cn(
                                      "ml-2 flex-shrink-0 rounded px-1.5 py-0.5 text-[10px]",
                                      statusStyles[subtaskStatus],
                                    )}
                                  >
                                    {statusLabels[subtaskStatus]}
                                  </span>
                                </button>

                                <AnimatePresence>
                                  {isSubtaskExpanded ? (
                                    <motion.div
                                      animate={{ height: "auto", opacity: 1 }}
                                      className="mt-1 ml-1.5 overflow-hidden border-foreground/20 border-l border-dashed pl-5 text-muted-foreground text-xs"
                                      exit={{ height: 0, opacity: 0 }}
                                      initial={{ height: 0, opacity: 0 }}
                                      transition={{ duration: 0.18 }}
                                    >
                                      {subtask.description ? <p className="py-1">{subtask.description}</p> : null}
                                      {subtask.meta?.length ? (
                                        <div className="mt-0.5 mb-1 flex flex-wrap gap-1">
                                          {subtask.meta.map((item) => (
                                            <Badge className="h-5 px-1.5 text-[10px]" key={item} variant="secondary">
                                              {item}
                                            </Badge>
                                          ))}
                                        </div>
                                      ) : null}
                                    </motion.div>
                                  ) : null}
                                </AnimatePresence>
                              </motion.li>
                            );
                          })}
                        </ul>
                      </motion.div>
                    ) : null}
                  </AnimatePresence>
                </motion.li>
              );
            })}
          </ul>
        </div>
      </LayoutGroup>
    </div>
  );
}
