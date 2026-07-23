"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChevronLeft, ChevronRight, Eye, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { RowActions } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type ApiTestPointOverview, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

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

const PAGE_SIZE = 10;

const PRIORITY_COLORS: Record<string, "destructive" | "secondary" | "outline"> = {
  P0: "destructive",
  P1: "secondary",
  P2: "outline",
  P3: "outline",
};

const CATEGORY_STYLES: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  功能测试: "default",
  边界测试: "secondary",
  异常测试: "destructive",
  性能测试: "outline",
  安全测试: "outline",
};

type TestPointRow = ApiTestPointOverview["points"][number];

interface TestPointsListProps {
  projectId: string;
  documentId: string;
  data: ApiTestPointOverview;
  canEdit: boolean;
  search?: string;
  onDataChange?: () => void;
  highlightedId?: string | null;
}

function TestPointDetailDialog({
  point,
  open,
  onOpenChange,
}: {
  point: TestPointRow | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  if (!point) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[88vh] w-[calc(100%-2rem)] overflow-hidden p-0"
        style={{ maxWidth: "56rem" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <div className="flex items-center gap-2">
            <Badge variant={PRIORITY_COLORS[point.priority] ?? "outline"} className="text-xs font-medium">
              {point.priority}
            </Badge>
            <Badge variant={CATEGORY_STYLES[point.category] ?? "outline"} className="text-xs font-medium">
              {point.category}
            </Badge>
            <DialogTitle className="sr-only">{point.title}</DialogTitle>
          </div>
        </div>

        {/* Title */}
        <div className="px-6 py-4 border-b">
          <h2 className="text-xl font-semibold leading-tight">{point.title}</h2>
          {point.module && (
            <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <span>模块</span>
              <span className="font-medium text-foreground">{point.module}</span>
            </div>
          )}
        </div>

        {/* Body */}
        <div className="overflow-y-auto px-6 py-4" style={{ maxHeight: "calc(88vh - 10rem)" }}>
          <div className="space-y-4">
            {/* 描述 & 前置条件 两列布局 */}
            <div className="grid gap-4 sm:grid-cols-2">
              {/* 描述卡片 */}
              <div className="rounded-lg border bg-card">
                <div className="px-4 py-2.5 border-b bg-muted/30">
                  <h4 className="font-medium text-sm">描述</h4>
                </div>
                <div className="p-4">
                  <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                    {point.description}
                  </p>
                </div>
              </div>

              {/* 前置条件卡片 */}
              <div className="rounded-lg border bg-card">
                <div className="px-4 py-2.5 border-b bg-muted/30">
                  <h4 className="font-medium text-sm">前置条件</h4>
                </div>
                <div className="p-4">
                  {point.preconditions.length > 0 ? (
                    <ul className="text-sm text-muted-foreground space-y-2">
                      {point.preconditions.map((item, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="text-primary mt-0.5 shrink-0">•</span>
                          <span className="leading-relaxed">{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">无</p>
                  )}
                </div>
              </div>
            </div>

            {/* 验证点卡片 */}
            <div className="rounded-lg border bg-card">
              <div className="px-4 py-2.5 border-b bg-muted/30">
                <h4 className="font-medium text-sm">验证点</h4>
              </div>
              <div className="p-4">
                {point.verification_points.length > 0 ? (
                  <ul className="text-sm text-muted-foreground space-y-2">
                    {point.verification_points.map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-primary mt-0.5 shrink-0">•</span>
                        <span className="leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">无</p>
                )}
              </div>
            </div>

            {/* 来源引用 & 备注 两列布局 */}
            <div className="grid gap-4 sm:grid-cols-2">
              {/* 来源引用卡片 */}
              {point.source_refs.length > 0 && (
                <div className="rounded-lg border bg-card">
                  <div className="px-4 py-2.5 border-b bg-muted/30">
                    <h4 className="font-medium text-sm">来源引用</h4>
                  </div>
                  <div className="p-4">
                    <ul className="text-sm text-muted-foreground space-y-2">
                      {point.source_refs.map((item, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="text-primary mt-0.5 shrink-0">•</span>
                          <span className="leading-relaxed">{item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* 备注卡片 */}
              {point.notes && (
                <div className="rounded-lg border bg-card border-l-4 border-l-amber-400/70">
                  <div className="px-4 py-2.5 border-b bg-amber-50/50 dark:bg-amber-900/20">
                    <div className="flex items-center gap-2">
                      <span className="text-amber-600 dark:text-amber-400">
                        <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                          <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </span>
                      <h4 className="font-medium text-sm text-amber-700 dark:text-amber-400">备注</h4>
                    </div>
                  </div>
                  <div className="p-4">
                    <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">{point.notes}</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TestPointsList({
  projectId,
  documentId,
  data,
  canEdit,
  search = "",
  onDataChange,
  highlightedId,
}: TestPointsListProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);

  const filteredPoints = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return data.points;
    return data.points.filter(
      (p) =>
        p.title.toLowerCase().includes(keyword) ||
        (p.module && p.module.toLowerCase().includes(keyword)) ||
        p.category.toLowerCase().includes(keyword)
    );
  }, [data.points, search]);

  const total = filteredPoints.length;
  const totalPages = Math.ceil(total / pageSize);
  const paginatedPoints = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredPoints.slice(start, start + pageSize);
  }, [filteredPoints, currentPage, pageSize]);

  const {
    rows: points,
    selectedIds,
    allSelected,
    partiallySelected,
    toggleAll,
    toggleOne,
    clearSelection,
    setRows,
  } = useLocalTableSelection<TestPointRow>(paginatedPoints);

  useEffect(() => {
    setRows(paginatedPoints);
  }, [paginatedPoints, setRows]);

  const [detailPoint, setDetailPoint] = useState<TestPointRow | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadPoints = useCallback(async () => {
    onDataChange?.();
  }, [onDataChange]);

  async function deletePoints(ids: string[]) {
    setDeleting(true);
    try {
      await Promise.all(
        ids.map((id) => apiRequest(`/projects/${projectId}/requirements/${documentId}/test-points/${id}`, { method: "DELETE" })),
      );
      clearSelection();
      await loadPoints();
      toast.success(`已删除 ${ids.length} 个测试点`);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "测试点删除失败",
        actionLabel: "删除测试点",
        method: "DELETE",
        path: `/projects/${projectId}/requirements/${documentId}/test-points/{id}`,
      });
    } finally {
      setDeleting(false);
    }
  }

  function openDetail(point: TestPointRow) {
    setDetailPoint(point);
    setDetailOpen(true);
  }

  if (data.points.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground text-sm">
        当前最终需求尚未生成测试点。
      </div>
    );
  }

  const visibleIds = points.map((p) => p.id);
  const visibleSelectedIds = selectedIds.filter((id) => visibleIds.includes(id));

  function goToPage(nextPage: number) {
    setCurrentPage(Math.min(Math.max(nextPage, 1), totalPages));
  }

  return (
    <>
      {canEdit && visibleSelectedIds.length > 0 ? (
        <div className="mb-3 flex justify-end">
          <Button disabled={deleting} onClick={() => deletePoints(visibleSelectedIds)} variant="outline">
            <Trash2 className="size-4" />
            批量删除 ({visibleSelectedIds.length})
          </Button>
        </div>
      ) : null}
        <div className="overflow-hidden rounded-lg border">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[5%]">
                  <Checkbox
                    aria-label="选择全部测试点"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={!canEdit || deleting}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead className="w-[42%]">标题</TableHead>
                <TableHead className="w-[10%]">优先级</TableHead>
                <TableHead className="w-[18%]">模块</TableHead>
                <TableHead className="w-[10%]">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {points.map((point) => (
                <TableRow
                  data-state={selectedIds.includes(point.id) ? "selected" : undefined}
                  key={point.id}
                  className={
                    highlightedId === point.id
                      ? "bg-blue-50/70 ring-1 ring-blue-200 dark:bg-blue-500/15 dark:ring-blue-500/30"
                      : undefined
                  }
                >
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${point.title}`}
                      checked={selectedIds.includes(point.id)}
                      disabled={!canEdit}
                      onCheckedChange={(checked) => toggleOne(point.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <button
                      className="block max-w-full truncate text-left hover:text-primary hover:underline"
                      onClick={() => openDetail(point)}
                      type="button"
                    >
                      {point.title}
                    </button>
                  </TableCell>
                  <TableCell>
                    <Badge variant={PRIORITY_COLORS[point.priority] ?? "outline"} className="text-xs">
                      {point.priority}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <OverflowTooltipText value={point.module || "-"} />
                  </TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        {
                          label: "查看详情",
                          icon: Eye,
                          onSelect: () => openDetail(point),
                        },
                        {
                          label: "删除",
                          destructive: true,
                          disabled: !canEdit,
                          icon: Trash2,
                          onSelect: canEdit ? () => deletePoints([point.id]) : undefined,
                        },
                      ]}
                      label={`打开 ${point.title} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {totalPages > 1 && (
          <div className="mt-4 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-end">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Pagination className="mx-0 w-auto justify-start sm:justify-end">
                <PaginationContent>
                  <PaginationItem className="mr-2 text-muted-foreground">共 {total} 条数据</PaginationItem>
                  <PaginationItem>
                    <PaginationButton
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      type="button"
                      variant="ghost"
                    >
                      <ChevronLeft className="rtl:rotate-180" /> 上一页
                    </PaginationButton>
                  </PaginationItem>
                  {getVisiblePages(currentPage, totalPages).map((item) =>
                    typeof item === "number" ? (
                      <PaginationItem key={item}>
                        <PaginationButton
                          aria-current={item === currentPage ? "page" : undefined}
                          mode="icon"
                          onClick={() => setCurrentPage(item)}
                          selected={item === currentPage}
                          type="button"
                          variant={item === currentPage ? "outline" : "ghost"}
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
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
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
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setCurrentPage(1);
                  }}
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
        )}

      <TestPointDetailDialog point={detailPoint} open={detailOpen} onOpenChange={setDetailOpen} />
    </>
  );
}

function OverflowTooltipText({ value }: { value: string }) {
  const textRef = useRef<HTMLSpanElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  useEffect(() => {
    const node = textRef.current;
    if (!node) {
      return;
    }

    const updateOverflowState = () => {
      setIsOverflowing(node.scrollWidth > node.clientWidth);
    };

    updateOverflowState();
    const resizeObserver = new ResizeObserver(updateOverflowState);
    resizeObserver.observe(node);
    return () => resizeObserver.disconnect();
  });

  const content = (
    <span ref={textRef} className="block truncate">
      {value}
    </span>
  );

  if (!value || !isOverflowing) {
    return content;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent className="max-w-sm whitespace-normal break-words leading-relaxed">{value}</TooltipContent>
    </Tooltip>
  );
}
