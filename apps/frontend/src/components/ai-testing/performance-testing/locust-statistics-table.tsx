"use client";

import { useMemo } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const STATISTICS_COLUMNS = [
  ["request", "名称"],
  ["request_count", "请求数"],
  ["failure_count", "失败数"],
  ["success_rate", "成功率"],
  ["requests_per_second", "RPS"],
  ["p50_response_time_ms", "P50"],
  ["p95_response_time_ms", "P95"],
  ["p99_response_time_ms", "P99"],
  ["min_response_time_ms", "最小响应时间"],
  ["max_response_time_ms", "最大响应时间"],
] as const;

export function LocustStatisticsTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const displayedRows = useMemo(
    () =>
      rows.slice(0, 501).map((row) => ({
        ...row,
        request: requestLabel(row),
        success_rate: successRate(row),
      })),
    [rows],
  );
  return <DataGrid columns={STATISTICS_COLUMNS} empty="暂无请求记录" rows={displayedRows} rowKey={rowKey} statistics />;
}

export function LocustGenericTable({
  rows,
  columns,
  empty,
}: {
  rows: Array<Record<string, unknown>>;
  columns: ReadonlyArray<readonly [string, string]>;
  empty: string;
}) {
  return (
    <DataGrid columns={columns} empty={empty} rows={rows} rowKey={(row, index) => `${JSON.stringify(row)}:${index}`} />
  );
}

function DataGrid({
  rows,
  columns,
  empty,
  rowKey,
  statistics = false,
}: {
  rows: Array<Record<string, unknown>>;
  columns: ReadonlyArray<readonly [string, string]>;
  empty: string;
  rowKey: (row: Record<string, unknown>, index: number) => string;
  statistics?: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-[0_8px_22px_-20px_rgba(15,23,42,0.45)] dark:border-slate-800 dark:bg-slate-900">
      <table
        className={
          statistics
            ? "w-full min-w-[1040px] table-fixed border-collapse text-left text-sm"
            : "w-full min-w-[900px] border-collapse text-left text-sm"
        }
      >
        {statistics ? (
          <colgroup>
            {columns.map(([key]) => (
              <col key={key} style={{ width: statisticsColumnWidth(key) }} />
            ))}
          </colgroup>
        ) : null}
        <thead className="bg-slate-50/80 text-slate-500 dark:bg-slate-950/40 dark:text-slate-400">
          <tr>
            {columns.map(([key, label]) => (
              <th
                className="whitespace-nowrap border-slate-200 border-b px-2 py-4 font-medium dark:border-slate-800"
                key={key}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.length ? (
            rows.map((row, index) => (
              <DataRow columns={columns} key={rowKey(row, index)} row={row} statistics={statistics} />
            ))
          ) : (
            <tr>
              <td className="px-4 py-12 text-center text-muted-foreground" colSpan={columns.length}>
                {empty}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function DataRow({
  row,
  columns,
  statistics,
}: {
  row: Record<string, unknown>;
  columns: ReadonlyArray<readonly [string, string]>;
  statistics: boolean;
}) {
  return (
    <tr className="border-slate-100 border-b last:border-b-0 hover:bg-emerald-50/30 dark:border-slate-800 dark:hover:bg-emerald-500/5">
      {columns.map(([key]) => (
        <td className="max-w-[420px] whitespace-nowrap px-2 py-4 align-middle" key={key}>
          {statistics && key === "request" ? <RequestName row={row} /> : null}
          {statistics && key === "success_rate" ? <SuccessRate value={row[key]} /> : null}
          {!statistics || (key !== "request" && key !== "success_rate") ? (
            <span className={key === "name" || key === "error" || key === "msg" ? "break-all" : "tabular-nums"}>
              {formatCell(row[key], key)}
            </span>
          ) : null}
        </td>
      ))}
    </tr>
  );
}

function RequestName({ row }: { row: Record<string, unknown> }) {
  const method = String(row.method ?? "").toUpperCase();
  const name = displayRequestName(row.name, method);
  return (
    <span className="flex min-w-[180px] items-center gap-2">
      {method ? <span className={methodBadgeClass(method)}>{method}</span> : null}
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="min-w-0 truncate font-medium text-slate-700 dark:text-slate-200">{name}</span>
        </TooltipTrigger>
        <TooltipContent className="max-w-md whitespace-normal break-all leading-5" side="top" sideOffset={6}>
          {name}
        </TooltipContent>
      </Tooltip>
    </span>
  );
}

function SuccessRate({ value }: { value: unknown }) {
  const rate = Number(value);
  return (
    <span className={rate < 99 ? "font-medium text-amber-600" : "font-medium text-emerald-600"}>
      {Number.isFinite(rate) ? `${rate.toFixed(2)}%` : "-"}
    </span>
  );
}

function requestLabel(row: Record<string, unknown>) {
  const method = String(row.method ?? "").toUpperCase();
  return `${method} ${displayRequestName(row.name, method)}`.trim();
}

function displayRequestName(value: unknown, method: string) {
  const name = String(value ?? "").trim();
  return method && name.toUpperCase().startsWith(`${method} `) ? name.slice(method.length + 1) : name || "-";
}

function successRate(row: Record<string, unknown>) {
  const requestCount = Number(row.request_count ?? 0);
  const failureCount = Number(row.failure_count ?? 0);
  return requestCount > 0 ? (1 - failureCount / requestCount) * 100 : 0;
}

function rowKey(row: Record<string, unknown>, index: number) {
  return `${index}:${String(row.method ?? "")}:${String(row.name ?? "")}`;
}

function statisticsColumnWidth(key: string) {
  const widths: Record<string, number> = {
    request: 300,
    request_count: 76,
    failure_count: 76,
    success_rate: 90,
    requests_per_second: 64,
    p50_response_time_ms: 76,
    p95_response_time_ms: 76,
    p99_response_time_ms: 76,
    min_response_time_ms: 118,
    max_response_time_ms: 118,
  };
  return widths[key];
}

function methodBadgeClass(method: string) {
  const base = "rounded px-2 py-0.5 font-semibold text-[11px]";
  if (method === "POST") return `${base} bg-sky-50 text-sky-600 dark:bg-sky-500/10 dark:text-sky-400`;
  if (method === "GET") return `${base} bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400`;
  if (method === "DELETE") return `${base} bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400`;
  return `${base} bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300`;
}

function formatCell(value: unknown, key?: string) {
  if (typeof value === "number") {
    const formatted = Number.isInteger(value) ? String(value) : value.toFixed(2);
    return key?.includes("response_time") || key?.startsWith("p") ? `${formatted} ms` : formatted;
  }
  return value === undefined || value === null || value === "" ? "-" : String(value);
}
