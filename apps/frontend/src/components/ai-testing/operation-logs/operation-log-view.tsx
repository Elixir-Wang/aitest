"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ChevronLeft, ChevronRight, Download, Eye, RefreshCw, Search } from "lucide-react";

import { OperationLogDetailContent } from "@/components/ai-testing/operation-logs/operation-log-detail-content";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem } from "@/components/ui/pagination";
import { operationLogResultTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiOperationLogDetail,
  type ApiOperationLogFilterOptions,
  type ApiOperationLogList,
  type ApiOperationLogListItem,
  type ApiProject,
  apiBlobRequest,
  apiRequest,
  formatDateTime,
  operationLogActionToLabel,
  operationLogModuleToLabel,
  operationLogResultToLabel,
} from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type OperationLogViewProps = {
  endpoint: string;
  showProjectFilter?: boolean;
};

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

function initialKeyword() {
  if (typeof window === "undefined") {
    return "";
  }
  return new URLSearchParams(window.location.search).get("keyword") ?? "";
}

export function OperationLogView({ endpoint, showProjectFilter = false }: OperationLogViewProps) {
  const [logs, setLogs] = useState<ApiOperationLogListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState(initialKeyword);
  const [module, setModule] = useState("");
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [filterOptions, setFilterOptions] = useState<ApiOperationLogFilterOptions | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiOperationLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), pageCount);
  const visiblePages = getVisiblePages(safePage, pageCount);
  const moduleOptions = useMemo(() => ["", ...(filterOptions?.modules ?? [])], [filterOptions?.modules]);
  const actionOptions = useMemo(() => ["", ...(filterOptions?.actions ?? [])], [filterOptions?.actions]);
  const resultOptions = useMemo(() => ["", ...(filterOptions?.results ?? [])], [filterOptions?.results]);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (keyword.trim()) {
      params.set("keyword", keyword.trim());
    }
    if (module) {
      params.set("module", module);
    }
    if (action) {
      params.set("action", action);
    }
    if (result) {
      params.set("result", result);
    }
    if (showProjectFilter && projectId) {
      params.set("project_id", projectId);
    }
    return params.toString();
  }, [action, keyword, module, page, pageSize, projectId, result, showProjectFilter]);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<ApiOperationLogList>(`${endpoint}?${query}`);
      setLogs(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "日志加载失败",
        actionLabel: "加载操作日志",
        method: "GET",
        path: `${endpoint}?${query}`,
      });
      setError(requestError instanceof Error ? requestError.message : "日志加载失败");
    } finally {
      setLoading(false);
    }
  }, [endpoint, query]);

  const loadFilterOptions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (showProjectFilter && projectId) {
        params.set("project_id", projectId);
      }
      const suffix = params.toString() ? `?${params.toString()}` : "";
      setFilterOptions(await apiRequest<ApiOperationLogFilterOptions>(`${endpoint}/filter-options${suffix}`));
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "日志筛选项加载失败",
        actionLabel: "加载日志筛选项",
        method: "GET",
        path: `${endpoint}/filter-options`,
      });
    }
  }, [endpoint, projectId, showProjectFilter]);

  const loadProjects = useCallback(async () => {
    if (!showProjectFilter) {
      return;
    }
    try {
      setProjects(await apiRequest<ApiProject[]>("/projects"));
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "项目筛选项加载失败",
        actionLabel: "加载项目筛选项",
        method: "GET",
        path: "/projects",
      });
    }
  }, [showProjectFilter]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    void loadFilterOptions();
  }, [loadFilterOptions]);

  useEffect(() => {
    if (!resultOptions.includes(result)) {
      setResult("");
    }
  }, [result, resultOptions]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function exportLogs() {
    setExporting(true);
    setError("");
    try {
      const exportQuery = queryForExport(query);
      const blob = await apiBlobRequest(`${endpoint}/export${exportQuery}`);
      downloadBlob(blob, showProjectFilter && projectId ? `${projectId}-operation-logs.csv` : "operation-logs.csv");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "日志导出失败",
        actionLabel: "导出操作日志",
        method: "GET",
        path: `${endpoint}/export`,
      });
      setError(requestError instanceof Error ? requestError.message : "日志导出失败");
    } finally {
      setExporting(false);
    }
  }

  async function openDetail(row: ApiOperationLogListItem) {
    setSelectedId(row.id);
    setDetail(null);
    setDetailLoading(true);
    setError("");
    try {
      setDetail(await apiRequest<ApiOperationLogDetail>(`/operation-logs/${row.id}`));
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "日志详情加载失败",
        actionLabel: "查看日志详情",
        method: "GET",
        path: `/operation-logs/${row.id}`,
      });
      setError(requestError instanceof Error ? requestError.message : "日志详情加载失败");
      setSelectedId(null);
    } finally {
      setDetailLoading(false);
    }
  }

  function goToPage(nextPage: number) {
    setPage(Math.min(Math.max(nextPage, 1), pageCount));
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
          {error}
        </div>
      ) : null}
      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-8"
              onChange={(event) => {
                setKeyword(event.target.value);
                setPage(1);
              }}
              placeholder="搜索对象、摘要或失败原因"
              value={keyword}
            />
          </div>
          <NativeSelect
            aria-label="模块"
            onChange={(event) => {
              setModule(event.target.value);
              setPage(1);
            }}
            value={module}
          >
            {moduleOptions.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogModuleToLabel(item) : "全部模块"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          {showProjectFilter ? (
            <NativeSelect
              aria-label="项目"
              onChange={(event) => {
                setProjectId(event.target.value);
                setPage(1);
              }}
              value={projectId}
            >
              <NativeSelectOption value="">全部项目</NativeSelectOption>
              {projects.map((project) => (
                <NativeSelectOption key={project.id} value={project.id}>
                  {project.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          ) : null}
          <NativeSelect
            aria-label="动作"
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            value={action}
          >
            {actionOptions.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogActionToLabel(item) : "全部动作"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="结果"
            onChange={(event) => {
              setResult(event.target.value);
              setPage(1);
            }}
            value={result}
          >
            {resultOptions.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogResultToLabel(item) : "全部结果"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button disabled={exporting} onClick={exportLogs} variant="outline">
            <Download className="size-4" />
            导出
          </Button>
          <Button onClick={loadLogs} variant="outline">
            <RefreshCw className="size-4" />
            刷新
          </Button>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <Table className="min-w-[1080px] table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[15%]">时间</TableHead>
              <TableHead className="w-[10%]">模块</TableHead>
              <TableHead className="w-[13%]">动作</TableHead>
              <TableHead className={showProjectFilter ? "w-[20%]" : "w-[24%]"}>对象</TableHead>
              <TableHead className="w-[10%]">结果</TableHead>
              <TableHead className="w-[26%]">摘要</TableHead>
              <TableHead className="w-[6%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((row) => {
              const moduleLabel = operationLogModuleToLabel(row.module);
              const actionLabel = operationLogActionToLabel(row.action);
              const objectLabel = row.object_name || row.object_id || "-";
              const summaryLabel =
                row.result === "failed" ? row.failure_reason || row.summary || "-" : row.summary || "-";
              const summaryTitle =
                row.result === "failed" && row.failure_reason && row.summary
                  ? `${row.summary}\n失败原因：${row.failure_reason}`
                  : summaryLabel;

              return (
                <TableRow key={row.id}>
                  <TableCell className="overflow-hidden text-muted-foreground text-xs">
                    <span className="block truncate">{formatDateTime(row.created_at)}</span>
                  </TableCell>
                  <TableCell className="overflow-hidden" title={moduleLabel}>
                    <span className="block truncate">{moduleLabel}</span>
                  </TableCell>
                  <TableCell className="overflow-hidden" title={actionLabel}>
                    <span className="block truncate">{actionLabel}</span>
                  </TableCell>
                  <TableCell className="overflow-hidden" title={objectLabel}>
                    <span className="block truncate">{objectLabel}</span>
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={operationLogResultTone(row.result)}>
                      {operationLogResultToLabel(row.result)}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="overflow-hidden" title={summaryTitle}>
                    <span className="block truncate">{summaryLabel}</span>
                  </TableCell>
                  <TableCell>
                    <Button aria-label="查看日志详情" onClick={() => openDetail(row)} size="icon-sm" variant="ghost">
                      <Eye className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
            {loading ? <TableLoadingRow colSpan={7} /> : null}
            {!loading && logs.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                  暂无操作日志。执行创建、编辑、删除或任务操作后，记录会显示在这里。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      <div className="flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-end">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Pagination className="mx-0 w-auto justify-start sm:justify-end">
            <PaginationContent>
              <PaginationItem className="mr-2 text-muted-foreground">共 {total} 条数据</PaginationItem>
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
              aria-label="每页显示条数"
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
      <Dialog
        open={Boolean(selectedId)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedId(null);
            setDetail(null);
          }
        }}
      >
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 sm:max-w-5xl">
          <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
            <DialogTitle>日志详情</DialogTitle>
            <DialogDescription>
              {detail
                ? `${operationLogModuleToLabel(detail.module)} / ${operationLogActionToLabel(detail.action)}`
                : "加载中"}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-4 overflow-auto px-6 pb-6">
            {detailLoading && !detail ? <div className="text-muted-foreground text-sm">正在加载日志详情</div> : null}
            {detail ? <OperationLogDetailContent detail={detail} /> : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function queryForExport(query: string) {
  const params = new URLSearchParams(query);
  params.delete("page");
  params.delete("page_size");
  const value = params.toString();
  return value ? `?${value}` : "";
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
