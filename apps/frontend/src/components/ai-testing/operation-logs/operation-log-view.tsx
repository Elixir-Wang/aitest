"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ChevronLeft, ChevronRight, Eye, RefreshCw, Search } from "lucide-react";

import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { OneClipboard } from "@/components/ui/one-clipboard";
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem } from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiOperationLogDetail,
  type ApiOperationLogList,
  type ApiOperationLogListItem,
  apiRequest,
  formatDateTime,
  operationLogActionToLabel,
  operationLogModuleToLabel,
  operationLogResultToLabel,
} from "@/lib/api-client";

type OperationLogViewProps = {
  endpoint: string;
  showProjectFilter?: boolean;
};

const modules = [
  "",
  "project",
  "requirement",
  "environment",
  "exploration",
  "knowledge",
  "operation_log",
  "system_setting",
  "model",
  "task",
  "auth",
  "agent",
  "user",
];
const actions = [
  "",
  "create",
  "update",
  "delete",
  "merge",
  "confirm",
  "cancel",
  "run",
  "start",
  "finish",
  "generate",
  "publish",
  "retry",
  "export",
  "login",
  "logout",
  "upload",
  "upload_global_knowledge",
  "update_global_knowledge",
  "create_global_knowledge_version",
  "archive_global_knowledge",
  "assign_model",
  "resolve_conflict",
  "update_retention_policy",
  "cleanup",
];
const results = ["", "success", "failed", "partial_success", "cancelled"];

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

export function OperationLogView({ endpoint, showProjectFilter = false }: OperationLogViewProps) {
  const [logs, setLogs] = useState<ApiOperationLogListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [module, setModule] = useState("");
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiOperationLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), pageCount);
  const visiblePages = getVisiblePages(safePage, pageCount);

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
    return params.toString();
  }, [action, keyword, module, page, pageSize, result]);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<ApiOperationLogList>(`${endpoint}?${query}`);
      setLogs(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "日志加载失败");
    } finally {
      setLoading(false);
    }
  }, [endpoint, query]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  async function openDetail(row: ApiOperationLogListItem) {
    setSelectedId(row.id);
    setDetail(null);
    setDetailLoading(true);
    setError("");
    try {
      setDetail(await apiRequest<ApiOperationLogDetail>(`/operation-logs/${row.id}`));
    } catch (requestError) {
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
            {modules.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogModuleToLabel(item) : "全部模块"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <NativeSelect
            aria-label="动作"
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            value={action}
          >
            {actions.map((item) => (
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
            {results.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogResultToLabel(item) : "全部结果"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <Button onClick={loadLogs} variant="outline">
          <RefreshCw className="size-4" />
          刷新
        </Button>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[15%]">时间</TableHead>
              <TableHead className="w-[10%]">模块</TableHead>
              <TableHead className="w-[9%]">动作</TableHead>
              <TableHead className={showProjectFilter ? "w-[22%]" : "w-[26%]"}>对象</TableHead>
              <TableHead className="w-[10%]">结果</TableHead>
              <TableHead className="w-[28%]">摘要</TableHead>
              <TableHead className="w-[6%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="truncate text-muted-foreground text-xs">
                  {formatDateTime(row.created_at)}
                </TableCell>
                <TableCell>{operationLogModuleToLabel(row.module)}</TableCell>
                <TableCell>{operationLogActionToLabel(row.action)}</TableCell>
                <TableCell className="truncate" title={row.object_name || row.object_id || ""}>
                  {row.object_name || row.object_id || "-"}
                </TableCell>
                <TableCell>
                  <Badge variant={row.result === "failed" ? "destructive" : "outline"}>
                    {operationLogResultToLabel(row.result)}
                  </Badge>
                </TableCell>
                <TableCell className="truncate" title={row.summary || row.failure_reason}>
                  {row.summary || row.failure_reason || "-"}
                </TableCell>
                <TableCell>
                  <Button aria-label="查看日志详情" onClick={() => openDetail(row)} size="icon-sm" variant="ghost">
                    <Eye className="size-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
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
            {detail ? (
              <>
                <DetailGrid detail={detail} />
                <JsonBlock title="变更前" value={detail.before} />
                <JsonBlock title="变更后" value={detail.after} />
                <JsonBlock title="关联产物" value={detail.artifact_path} />
              </>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DetailGrid({ detail }: { detail: ApiOperationLogDetail }) {
  const rows: Array<[string, string]> = [
    ["时间", formatDateTime(detail.created_at)],
    ["对象", detail.object_name || detail.object_id || "-"],
    ["操作人", detail.actor_name],
    ["结果", operationLogResultToLabel(detail.result)],
    ["摘要", detail.summary || "-"],
    ["失败原因", detail.failure_reason || "-"],
    ["任务 ID", detail.task_id || "-"],
    ["请求 ID", detail.request_id || "-"],
    ["IP", detail.ip_address || "-"],
    ["User-Agent", detail.user_agent || "-"],
  ];

  return (
    <div className="relative min-w-0 rounded-lg border p-4 pr-28 text-sm">
      <div className="absolute top-4 right-4">
        <OneClipboard copiedLabel="已复制" label="复制" text={serializeDetailRows(rows)} />
      </div>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-medium text-sm">基础信息</h2>
      </div>
      <div className="grid min-w-0 gap-3">
        {rows.map(([label, value]) => (
          <div className="grid min-w-0 gap-1 md:grid-cols-[120px_minmax(0,1fr)] md:gap-4" key={label}>
            <span className="text-muted-foreground">{label}</span>
            <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
              {label === "结果" ? (
                <Badge variant={detail.result === "failed" ? "destructive" : "outline"}>{value}</Badge>
              ) : (
                value
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const text = JSON.stringify(value ?? {}, null, 2);

  return (
    <section className="space-y-2">
      <h2 className="font-medium text-sm">{title}</h2>
      <div className="relative min-w-0 rounded-lg border bg-muted/30">
        <div className="absolute top-3 right-3">
          <OneClipboard copiedLabel="已复制" label="复制" text={text} />
        </div>
        <pre className="min-w-0 overflow-auto whitespace-pre-wrap break-words p-4 pr-28 text-xs [overflow-wrap:anywhere]">
          {text}
        </pre>
      </div>
    </section>
  );
}

function serializeDetailRows(rows: Array<[string, string]>) {
  return rows.map(([label, value]) => `${label}：${value}`).join("\n");
}
