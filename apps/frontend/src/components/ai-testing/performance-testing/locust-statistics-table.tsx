"use client";

import { useMemo } from "react";

const COLUMNS = [
  ["method", "Type"],
  ["name", "Name"],
  ["request_count", "Requests"],
  ["failure_count", "Fails"],
  ["median_response_time_ms", "Median (ms)"],
  ["p95_response_time_ms", "95%ile (ms)"],
  ["p99_response_time_ms", "99%ile (ms)"],
  ["average_response_time_ms", "Average (ms)"],
  ["min_response_time_ms", "Min (ms)"],
  ["max_response_time_ms", "Max (ms)"],
  ["content_size", "Average size (bytes)"],
  ["requests_per_second", "Current RPS"],
] as const;

export function LocustStatisticsTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const displayedRows = useMemo(() => rows.slice(0, 501), [rows]);
  return (
    <DataGrid
      columns={COLUMNS}
      empty="No requests have been recorded."
      rows={displayedRows}
      rowKey={(row, index) => `${index}:${String(row.method ?? "")}:${String(row.name ?? "")}`}
    />
  );
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
    <DataGrid
      columns={columns}
      empty={empty}
      rows={rows}
      rowKey={(row, index) => JSON.stringify(row) + ":" + index}
    />
  );
}

function DataGrid({
  rows,
  columns,
  empty,
  rowKey,
}: {
  rows: Array<Record<string, unknown>>;
  columns: ReadonlyArray<readonly [string, string]>;
  empty: string;
  rowKey: (row: Record<string, unknown>, index: number) => string;
}) {
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full min-w-[900px] border-collapse text-left text-xs">
        <thead className="bg-muted/40 text-muted-foreground">
          <tr>
            {columns.map(([key, label]) => (
              <th className="border-b px-3 py-2.5 font-medium" key={key}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.length ? (
            rows.map((row, index) => (
              <tr className="hover:bg-muted/20" key={rowKey(row, index)}>
                {columns.map(([key]) => (
                  <td className="max-w-[420px] px-3 py-2.5 align-top" key={key}>
                    <span className={key === "name" || key === "error" || key === "msg" ? "break-all" : "tabular-nums"}>
                      {formatCell(row[key])}
                    </span>
                  </td>
                ))}
              </tr>
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

function formatCell(value: unknown) {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return value === undefined || value === null || value === "" ? "-" : String(value);
}
