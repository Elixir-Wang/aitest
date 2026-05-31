"use client";

import { useEffect, useMemo, useState } from "react";

import { AnimatePresence, LayoutGroup, motion, type Variants, useReducedMotion } from "motion/react";
import { CheckCircle2, Circle, CircleAlert, CircleDotDashed, CircleX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AgentPlanStatus =
  | "pending"
  | "queued"
  | "in-progress"
  | "running"
  | "stopping"
  | "completed"
  | "partial"
  | "blocked"
  | "waiting_human"
  | "cancelled"
  | "failed";

export type AgentPlanStep = {
  id: string;
  title: string;
  detail?: string;
  status?: AgentPlanStatus;
  meta?: string[];
};

export type AgentPlanSubtask = {
  id: string;
  title: string;
  description?: string;
  status: AgentPlanStatus;
  meta?: string[];
  steps?: AgentPlanStep[];
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
  completedTaskDecoration?: "line-through" | "none";
};

const statusLabels: Record<AgentPlanStatus, string> = {
  pending: "待探索",
  queued: "排队中",
  "in-progress": "探索中",
  running: "探索中",
  stopping: "正在停止",
  completed: "已完成",
  partial: "部分完成",
  blocked: "阻塞",
  waiting_human: "等待人工",
  cancelled: "已中止",
  failed: "失败",
};

const statusStyles: Record<AgentPlanStatus, string> = {
  pending: "bg-muted text-muted-foreground",
  queued: "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  "in-progress": "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  stopping: "bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  partial: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  blocked: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  waiting_human: "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  cancelled: "bg-muted text-muted-foreground",
  failed: "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300",
};

function normalizeStatus(status: string): AgentPlanStatus {
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
  if (normalized === "in-progress" || normalized === "running" || normalized === "queued" || normalized === "stopping") {
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
  if (normalized === "partial" || normalized === "cancelled" || normalized === "waiting_human") {
    return <CircleAlert className={cn(className, "text-amber-500")} />;
  }
  if (normalized === "blocked" || normalized === "failed") {
    return <CircleX className={cn(className, "text-red-500")} />;
  }
  return <Circle className={cn(className, "text-muted-foreground")} />;
}

export function AgentPlan({
  tasks,
  defaultExpandedTaskIds,
  emptyLabel = "暂无探索模块",
  className,
  completedTaskDecoration = "line-through",
}: AgentPlanProps) {
  const prefersReducedMotion = useReducedMotion();
  const initialExpanded = useMemo(() => {
    if (defaultExpandedTaskIds?.length) {
      return defaultExpandedTaskIds;
    }
    return tasks.slice(0, 1).map((task) => task.id);
  }, [defaultExpandedTaskIds, tasks]);
  const [expandedTasks, setExpandedTasks] = useState<string[]>(initialExpanded);
  const [expandedSubtasks, setExpandedSubtasks] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setExpandedTasks((current) => {
      if (current.length || tasks.length === 0) {
        return current;
      }
      return tasks.slice(0, 1).map((task) => task.id);
    });
  }, [tasks]);

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

  const taskVariants: Variants = {
    hidden: {
      opacity: 0,
      y: prefersReducedMotion ? 0 : -5,
    },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        type: prefersReducedMotion ? "tween" : "spring",
        stiffness: 500,
        damping: 30,
        duration: prefersReducedMotion ? 0.2 : undefined,
      },
    },
  };

  const subtaskListVariants: Variants = {
    hidden: {
      height: 0,
      opacity: 0,
      overflow: "hidden",
    },
    visible: {
      height: "auto",
      opacity: 1,
      overflow: "visible",
      transition: {
        duration: 0.25,
        ease: [0.2, 0.65, 0.3, 0.9] as const,
        staggerChildren: prefersReducedMotion ? 0 : 0.05,
        when: "beforeChildren",
      },
    },
  };

  const subtaskVariants: Variants = {
    hidden: {
      opacity: 0,
      x: prefersReducedMotion ? 0 : -10,
    },
    visible: {
      opacity: 1,
      x: 0,
      transition: {
        type: prefersReducedMotion ? "tween" : "spring",
        stiffness: 500,
        damping: 25,
        duration: prefersReducedMotion ? 0.2 : undefined,
      },
    },
  };

  return (
    <div className={cn("h-full overflow-hidden text-foreground", className)}>
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="overflow-hidden text-card-foreground"
        initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 10 }}
        transition={{ duration: 0.3, ease: [0.2, 0.65, 0.3, 0.9] }}
      >
        <LayoutGroup>
          <div className="overflow-hidden">
            <ul className="space-y-1 overflow-hidden">
              {tasks.map((task, index) => {
                const taskStatus = normalizeStatus(task.status);
                const isExpanded = expandedTasks.includes(task.id);
                const isCompleted = taskStatus === "completed";
                return (
                  <motion.li
                    animate="visible"
                    className={cn(index !== 0 && "mt-1 pt-2")}
                    initial="hidden"
                    key={task.id}
                    variants={taskVariants}
                  >
                    <motion.div
                      className="group flex min-w-0 items-center rounded-md px-3 py-1.5"
                      whileHover={{ backgroundColor: "rgba(0,0,0,0.03)", transition: { duration: 0.2 } }}
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
                      <div className="mr-2 min-w-0 flex-1">
                        <div
                          className={cn(
                            "truncate font-medium text-sm",
                            isCompleted && "text-muted-foreground",
                            isCompleted && completedTaskDecoration === "line-through" && "line-through",
                          )}
                        >
                          {task.title}
                        </div>
                        {task.description ? <div className="truncate text-muted-foreground text-xs">{task.description}</div> : null}
                      </div>
                      <div className="flex flex-shrink-0 items-center space-x-2 text-xs">
                        {task.dependencies?.length ? (
                          <div className="mr-2 flex flex-wrap gap-1">
                            {task.dependencies.map((dependency) => (
                              <motion.span
                                animate={{ opacity: 1, scale: 1 }}
                                className="rounded bg-secondary/40 px-1.5 py-0.5 font-medium text-[10px] text-secondary-foreground shadow-sm"
                                initial={{ opacity: 0, scale: 0.9 }}
                                key={dependency}
                                transition={{ duration: 0.2 }}
                                whileHover={{ backgroundColor: "rgba(0,0,0,0.1)", y: prefersReducedMotion ? 0 : -1 }}
                              >
                                {dependency}
                              </motion.span>
                            ))}
                          </div>
                        ) : null}
                        {task.meta?.map((item) => (
                          <Badge className="h-5 px-1.5 text-[10px]" key={item} variant="secondary">
                            {item}
                          </Badge>
                        ))}
                        <motion.span
                          animate={{ scale: prefersReducedMotion ? 1 : [1, 1.08, 1] }}
                          className={cn("rounded px-1.5 py-0.5", statusStyles[taskStatus])}
                          key={taskStatus}
                          transition={{ duration: 0.35, ease: [0.34, 1.56, 0.64, 1] }}
                        >
                          {statusLabels[taskStatus]}
                        </motion.span>
                      </div>
                    </button>
                  </motion.div>

                  <AnimatePresence mode="wait">
                    {isExpanded && task.subtasks?.length ? (
                      <motion.div
                        animate="visible"
                        className="relative overflow-hidden"
                        exit="hidden"
                        initial="hidden"
                        layout
                        variants={subtaskListVariants}
                      >
                        <div className="absolute top-0 bottom-0 left-[20px] border-muted-foreground/30 border-l-2 border-dashed" />
                        <ul className="mt-1 mr-2 mb-1.5 ml-3 space-y-0.5 border-muted">
                          {task.subtasks.map((subtask) => {
                            const subtaskStatus = normalizeStatus(subtask.status);
                            const subtaskKey = `${task.id}-${subtask.id}`;
                            const isSubtaskExpanded = expandedSubtasks[subtaskKey];
                            const isSubtaskCompleted = subtaskStatus === "completed";
                            return (
                              <motion.li
                                animate="visible"
                                className="group flex min-w-0 flex-col py-0.5 pl-6"
                                initial="hidden"
                                key={subtask.id}
                                layout
                                variants={subtaskVariants}
                              >
                                <button
                                  className="flex min-w-0 flex-1 items-center rounded-md p-1 text-left"
                                  onClick={() => toggleSubtaskExpansion(task.id, subtask.id)}
                                  type="button"
                                >
                                  <span className="mr-2 flex-shrink-0">
                                    <StatusIcon status={subtaskStatus} subtask />
                                  </span>
                                  <span
                                    className={cn(
                                      "min-w-0 flex-1 truncate text-sm",
                                      isSubtaskCompleted && "text-muted-foreground",
                                      isSubtaskCompleted && completedTaskDecoration === "line-through" && "line-through",
                                    )}
                                  >
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
                                      layout
                                      transition={{ duration: 0.25, ease: [0.2, 0.65, 0.3, 0.9] }}
                                    >
                                      {subtask.description ? <p className="py-1">{subtask.description}</p> : null}
                                      {subtask.steps?.length ? (
                                        <ul className="space-y-1 py-1">
                                          {subtask.steps.slice(0, 20).map((step) => {
                                            const stepStatus = normalizeStatus(step.status || "completed");
                                            return (
                                              <li className="flex min-w-0 items-start gap-2" key={step.id}>
                                                <span className="mt-0.5 flex-shrink-0">
                                                  <StatusIcon status={stepStatus} subtask />
                                                </span>
                                                <span className="min-w-0 flex-1">
                                                  <span className="text-foreground/80">{step.title}</span>
                                                  {step.detail ? <span>：{step.detail}</span> : null}
                                                </span>
                                              </li>
                                            );
                                          })}
                                        </ul>
                                      ) : null}
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
      </motion.div>
    </div>
  );
}
