"use client";

import * as React from "react";
import { ChevronLeftIcon, ChevronRightIcon, MoreHorizontalIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type PageItem = number | "ellipsis-start" | "ellipsis-end";

function Pagination({ className, ...props }: React.ComponentProps<"nav">) {
  return (
    <nav
      aria-label="pagination"
      className={cn("mx-auto flex w-full justify-center", className)}
      data-slot="pagination"
      role="navigation"
      {...props}
    />
  );
}

function PaginationContent({ className, ...props }: React.ComponentProps<"ul">) {
  return <ul className={cn("flex flex-row items-center gap-1", className)} data-slot="pagination-content" {...props} />;
}

function PaginationItem({ className, ...props }: React.ComponentProps<"li">) {
  return <li className={cn("", className)} data-slot="pagination-item" {...props} />;
}

function PaginationEllipsis({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      aria-hidden
      className={cn("flex size-9 items-center justify-center", className)}
      data-slot="pagination-ellipsis"
      {...props}
    >
      <MoreHorizontalIcon className="size-4" />
      <span className="sr-only">更多页码</span>
    </span>
  );
}

type ListPaginationProps = {
  className?: string;
  currentPage: number;
  itemName?: string;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  pageSize: number;
  pageSizeOptions?: number[];
  total: number;
};

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

export function ListPagination({
  className,
  currentPage,
  itemName = "条",
  onPageChange,
  onPageSizeChange,
  pageSize,
  pageSizeOptions = [10, 20, 50, 100],
  total,
}: ListPaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(currentPage, 1), pageCount);
  const visiblePages = getVisiblePages(safePage, pageCount);

  function goToPage(page: number) {
    onPageChange(Math.min(Math.max(page, 1), pageCount));
  }

  return (
    <div className={cn("flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between", className)}>
      <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
        <span>共 {total} {itemName}</span>
        <label className="flex items-center gap-1">
          <span>每页</span>
          <select
            aria-label="每页显示条数"
            className="h-8 rounded-md border border-input bg-background px-2 text-foreground text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!onPageSizeChange}
            onChange={(event) => onPageSizeChange?.(Number(event.target.value))}
            value={pageSize}
          >
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option} 条
              </option>
            ))}
          </select>
        </label>
        <span>第 {safePage} / {pageCount} 页</span>
      </div>
      <Pagination className="mx-0 w-auto justify-start sm:justify-end">
        <PaginationContent>
          <PaginationItem>
            <button
              aria-label="上一页"
              className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40"
              disabled={safePage <= 1}
              onClick={() => goToPage(safePage - 1)}
              type="button"
            >
              <ChevronLeftIcon className="size-4" />
              上一页
            </button>
          </PaginationItem>
          {visiblePages.map((item) =>
            typeof item === "number" ? (
              <PaginationItem key={item}>
                <button
                  aria-current={item === safePage ? "page" : undefined}
                  aria-label={`第 ${item} 页`}
                  className={cn(
                    "inline-flex size-8 items-center justify-center rounded-md border border-transparent text-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                    item === safePage && "border-primary/25 bg-primary/10 text-primary hover:bg-primary/15",
                  )}
                  onClick={() => goToPage(item)}
                  type="button"
                >
                  {item}
                </button>
              </PaginationItem>
            ) : (
              <PaginationItem key={item}>
                <PaginationEllipsis className="size-8 text-muted-foreground" />
              </PaginationItem>
            ),
          )}
          <PaginationItem>
            <button
              aria-label="下一页"
              className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40"
              disabled={safePage >= pageCount}
              onClick={() => goToPage(safePage + 1)}
              type="button"
            >
              下一页
              <ChevronRightIcon className="size-4" />
            </button>
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}

export { Pagination, PaginationContent, PaginationEllipsis, PaginationItem };
