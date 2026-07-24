"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { RowActions } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Button as PaginationButton } from "@/components/ui/button-1";
import { Checkbox } from "@/components/ui/checkbox";
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem } from "@/components/ui/pagination";
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

const PAGE_SIZE = 15;

const PRIORITY_COLORS: Record<string, "destructive" | "secondary" | "outline"> = {
  P0: "destructive",
  P1: "secondary",
  P2: "outline",
  P3: "outline",
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
        p.module?.toLowerCase().includes(keyword) ||
        p.priority.toLowerCase().includes(keyword),
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

  const [deleting, setDeleting] = useState(false);

  const loadPoints = useCallback(async () => {
    onDataChange?.();
  }, [onDataChange]);

  async function deletePoints(ids: string[]) {
    setDeleting(true);
    try {
      await Promise.all(
        ids.map((id) =>
          apiRequest(`/projects/${projectId}/requirements/${documentId}/test-points/${id}`, { method: "DELETE" }),
        ),
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

  if (data.points.length === 0) {
    return <div className="py-12 text-center text-muted-foreground text-sm">当前最终需求尚未生成测试点。</div>;
  }

  const visibleIds = points.map((p) => p.id);
  const visibleSelectedIds = selectedIds.filter((id) => visibleIds.includes(id));

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
                  <span className="block max-w-full truncate">{point.title}</span>
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
