"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Clock3, Eye, ListTodo } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { ProcessingState } from "@/components/ai-testing/table-loading-row";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem } from "@/components/ui/pagination";
import { StatusBadge, taskStatusTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type ApiTaskItem, type ApiTaskList, apiRequest, formatDateTime } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import { useProjectContextStore } from "@/stores/project-context-store";

function TaskStatusBadge({ task }: { task: ApiTaskItem }) {
  const isRunning = task.status_group === "running";

  return (
    <StatusBadge tone={taskStatusTone(task.status_group, task.status)}>
      {isRunning || task.status === "processing" ? <ProcessingState label={task.status_label} /> : task.status_label}
    </StatusBadge>
  );
}

const TASK_SOURCE_TYPE_LABELS: Record<string, string> = {
  exploration_run: "Playwright 探索任务",
  requirement_file: "需求文件上传转换",
  requirement_analysis_run: "AI 需求分析任务",
  requirement_finalization_run: "需求定稿",
  test_case_generation_run: "用例集生成任务",
  test_point_generation_run: "测试点生成任务",
  api_automation_generation_run: "接口用例生成",
  api_script_generation_run: "接口脚本生成",
  api_automation_run: "接口自动化执行",
};

function getTaskSourceTypeLabel(sourceType: string) {
  return TASK_SOURCE_TYPE_LABELS[sourceType] ?? sourceType;
}

function OverflowTooltipText({ value }: { value: string }) {
  const textRef = useRef<HTMLSpanElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  useLayoutEffect(() => {
    const node = textRef.current;
    if (!node) return;

    const updateOverflowState = () => setIsOverflowing(node.scrollWidth > node.clientWidth + 1);
    updateOverflowState();

    const resizeObserver = new ResizeObserver(updateOverflowState);
    resizeObserver.observe(node);
    return () => resizeObserver.disconnect();
  }, [value]);

  const content = (
    <span ref={textRef} className="block min-w-0 truncate" tabIndex={isOverflowing ? 0 : undefined}>
      {value}
    </span>
  );

  if (!value || !isOverflowing) return content;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent className="max-w-md whitespace-normal break-words leading-5" side="top" sideOffset={6}>
        {value}
      </TooltipContent>
    </Tooltip>
  );
}

type PageItem = number | "ellipsis-start" | "ellipsis-end";

function getVisiblePages(currentPage: number, pageCount: number): PageItem[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "ellipsis-end", pageCount];
  }

  if (currentPage >= pageCount - 3) {
    return [1, "ellipsis-start", pageCount - 4, pageCount - 3, pageCount - 2, pageCount - 1, pageCount];
  }

  return [1, "ellipsis-start", currentPage - 1, currentPage, currentPage + 1, "ellipsis-end", pageCount];
}

export default function Page() {
  const { currentProjectId, hydrate, scope } = useProjectContextStore();
  const { hasHydrated: hasAuthHydrated, hydrate: hydrateAuth, token } = useAuthStore();
  const [tasks, setTasks] = useState<ApiTaskItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedTask, setSelectedTask] = useState<ApiTaskItem | null>(null);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), pageCount);
  const visiblePages = getVisiblePages(safePage, pageCount);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  const loadTasks = useCallback(async () => {
    if (!hasAuthHydrated || !token) {
      setTasks([]);
      setError("");
      return;
    }

    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (scope === "project" && currentProjectId) {
        params.set("project_id", currentProjectId);
      }
      if (searchText.trim()) {
        params.set("keyword", searchText.trim());
      }
      const data = await apiRequest<ApiTaskList>(`/tasks?${params.toString()}`);
      setTasks(data.items);
      setTotal(data.total);
      setPage(data.page);
      setError("");
    } catch (requestError) {
      setTasks([]);
      setTotal(0);
      setError(requestError instanceof Error ? requestError.message : "任务列表加载失败");
    }
  }, [currentProjectId, hasAuthHydrated, page, pageSize, scope, searchText, token]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  function goToPage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  }

  const metrics = useMemo(() => {
    const runningCount = tasks.filter((task) => task.status_group === "running").length;
    const waitingCount = tasks.filter((task) => task.status_group === "waiting").length;
    const failedCount = tasks.filter((task) => task.status_group === "failed").length;
    return { runningCount, waitingCount, failedCount };
  }, [tasks]);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("tasks")}
      description="汇总需求分析、探索、知识库、用例、UI 自动化和失败诊断任务。"
      projectScope="all"
      tabs={["全部任务", "等待人工", "失败任务"]}
      title="任务中心"
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard helper="当前可见任务数量" icon={ListTodo} label="全部任务" value={String(total)} />
        <MetricCard helper="正在执行的后台任务" icon={Clock3} label="运行中" value={String(metrics.runningCount)} />
        <MetricCard
          helper="需要人工继续处理"
          icon={AlertTriangle}
          label="等待人工"
          value={String(metrics.waitingCount)}
        />
        <MetricCard helper="需要排查或重试" icon={CheckCircle2} label="失败任务" value={String(metrics.failedCount)} />
      </div>
      <ShellSection>
        <ListToolbar
          onSearch={(value) => {
            setSearchText(value);
            setPage(1);
          }}
          placeholder="搜索任务种类、模块或项目"
          title="任务列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table className="min-w-[980px] table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[34%]">任务名称</TableHead>
                <TableHead className="w-[14%]">任务种类</TableHead>
                <TableHead className="w-[12%]">项目</TableHead>
                <TableHead className="w-[14%]">状态</TableHead>
                <TableHead className="w-[20%]">更新时间</TableHead>
                <TableHead className="w-[6%]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tasks.map((task) => (
                <TableRow key={task.id}>
                  <TableCell className="overflow-hidden font-medium">
                    <OverflowTooltipText value={task.title} />
                  </TableCell>
                  <TableCell>{task.module_label}</TableCell>
                  <TableCell>{task.project_name}</TableCell>
                  <TableCell>
                    <TaskStatusBadge task={task} />
                  </TableCell>
                  <TableCell>{formatDateTime(task.updated_at)}</TableCell>
                  <TableCell>
                    <Button
                      aria-label="查看任务详情"
                      onClick={() => setSelectedTask(task)}
                      size="icon-sm"
                      variant="ghost"
                    >
                      <Eye className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {tasks.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    {error || "暂无任务。发起需求分析、站点探索或自动化执行后，任务进度会显示在这里。"}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
        <div className="flex flex-col gap-3 pt-4 text-sm sm:flex-row sm:items-center sm:justify-end">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Pagination className="mx-0 w-auto justify-start sm:justify-end">
              <PaginationContent>
                <PaginationItem className="mr-2 text-muted-foreground">共 {total} 个任务</PaginationItem>
                <PaginationItem>
                  <PaginationButton
                    disabled={safePage <= 1}
                    onClick={() => goToPage(safePage - 1)}
                    type="button"
                    variant="ghost"
                  >
                    <ChevronLeft className="rtl:rotate-180" /> 上一页
                  </PaginationButton>
                </PaginationItem>
                {visiblePages.map((item) =>
                  typeof item === "number" ? (
                    <PaginationItem key={item}>
                      <PaginationButton
                        aria-current={item === safePage ? "page" : undefined}
                        mode="icon"
                        onClick={() => goToPage(item)}
                        selected={item === safePage}
                        type="button"
                        variant={item === safePage ? "outline" : "ghost"}
                      >
                        {item}
                      </PaginationButton>
                    </PaginationItem>
                  ) : (
                    <PaginationItem key={item}>
                      <PaginationEllipsis />
                    </PaginationItem>
                  ),
                )}
                <PaginationItem>
                  <PaginationButton
                    disabled={safePage >= pageCount}
                    onClick={() => goToPage(safePage + 1)}
                    type="button"
                    variant="ghost"
                  >
                    下一页 <ChevronRight className="rtl:rotate-180" />
                  </PaginationButton>
                </PaginationItem>
              </PaginationContent>
            </Pagination>
            <label className="flex items-center gap-1 text-muted-foreground">
              <span>每页</span>
              <select
                aria-label="每页显示任务数"
                className="h-8 rounded-md border border-input bg-background px-2 text-foreground text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                value={pageSize}
              >
                {[10, 15, 20, 50, 100].map((option) => (
                  <option key={option} value={option}>
                    {option} 条
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </ShellSection>
      <Dialog open={Boolean(selectedTask)} onOpenChange={(open) => !open && setSelectedTask(null)}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-2xl">
          <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
            <DialogTitle>任务详情</DialogTitle>
            <DialogDescription>
              {selectedTask ? `${selectedTask.module_label} / ${selectedTask.status_label}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 overflow-auto px-6 pb-6">
            {selectedTask ? <TaskDetail task={selectedTask} /> : null}
          </div>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function TaskDetail({ task }: { task: ApiTaskItem }) {
  const rows: Array<[string, string]> = [
    ["项目", task.project_name],
    ["任务种类", task.module_label],
    ["任务名称", task.title],
    ["状态", task.status_label],
    ["更新时间", formatDateTime(task.updated_at)],
    ["任务 ID", task.source_id],
    ["任务来源", getTaskSourceTypeLabel(task.source_type)],
    ["摘要", task.summary || "-"],
    ["详情地址", task.detail_url || "-"],
  ];

  return (
    <div className="relative grid gap-3 rounded-lg border p-4 pr-28 text-sm">
      <div className="absolute top-4 right-4">
        <OneClipboard text={serializeTaskDetailRows(rows)} />
      </div>
      {rows.map(([label, value]) => (
        <div className="grid min-w-0 gap-1 md:grid-cols-[96px_minmax(0,1fr)] md:gap-4" key={label}>
          <span className="text-muted-foreground">{label}</span>
          <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
            {label === "状态" ? <TaskStatusBadge task={task} /> : value}
          </span>
        </div>
      ))}
    </div>
  );
}

function serializeTaskDetailRows(rows: Array<[string, string]>) {
  return rows.map(([label, value]) => `${label}：${value}`).join("\n");
}
