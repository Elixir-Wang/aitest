"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ApiRequestError,
  getPerformanceRun,
  getPerformanceRunStats,
  listPerformanceRunReports,
  type PerformanceRun,
  type PerformanceRunReports,
  type PerformanceRunStats,
  performanceRunReportUrl,
  stopPerformanceRun,
  streamPerformanceRun,
} from "@/lib/api-client";

const TERMINAL_STATUSES = new Set(["completed", "stopped", "failed", "cancelled"]);

export function PerformanceRunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const [run, setRun] = useState<PerformanceRun | null>(null);
  const [snapshot, setSnapshot] = useState<PerformanceRunStats | null>(null);
  const [reports, setReports] = useState<PerformanceRunReports | null>(null);
  const [loading, setLoading] = useState(true);
  const [stopping, setStopping] = useState(false);
  const runRef = useRef<PerformanceRun | null>(null);

  const refresh = useCallback(async () => {
    const [runResult, statsResult, reportsResult] = await Promise.all([
      getPerformanceRun(projectId, runId),
      getPerformanceRunStats(projectId, runId),
      listPerformanceRunReports(projectId, runId),
    ]);
    runRef.current = runResult;
    setRun(runResult);
    setSnapshot(statsResult);
    setReports(reportsResult);
  }, [projectId, runId]);

  useEffect(() => {
    let disposed = false;
    let fallbackTimer: number | undefined;
    const controller = new AbortController();
    const startPollingFallback = () => {
      if (fallbackTimer !== undefined) return;
      fallbackTimer = window.setInterval(() => {
        if (!disposed && (!runRef.current || !TERMINAL_STATUSES.has(runRef.current.status))) {
          refresh().catch((error) => {
            if (!disposed) toast.error(apiErrorMessage(error));
          });
        }
      }, 1000);
    };
    setLoading(true);
    refresh()
      .catch((error) => {
        if (!disposed) toast.error(apiErrorMessage(error));
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    streamPerformanceRun(projectId, runId, controller.signal, (event, payload) => {
      if (disposed) return;
      if (event === "run") {
        runRef.current = payload as unknown as PerformanceRun;
        setRun(payload as unknown as PerformanceRun);
      } else if (event === "stats") {
        runRef.current = payload.run as unknown as PerformanceRun;
        setRun(payload.run as unknown as PerformanceRun);
        setSnapshot((current) =>
          current
            ? {
                ...current,
                run: payload.run as unknown as PerformanceRun,
                stats: [...current.stats, payload.latest as Record<string, unknown>],
                failures: (payload.failures as Array<Record<string, unknown>>) ?? current.failures,
                exceptions: (payload.exceptions as Array<Record<string, unknown>>) ?? current.exceptions,
              }
            : current,
        );
      } else if (event === "log") {
        setSnapshot((current) => (current ? { ...current, events: [...current.events, payload] } : current));
      }
    }).catch((error) => {
      if (!disposed && (error as Error)?.name !== "AbortError") startPollingFallback();
    });
    return () => {
      disposed = true;
      controller.abort();
      if (fallbackTimer !== undefined) window.clearInterval(fallbackTimer);
    };
  }, [projectId, refresh, runId]);

  const latest = snapshot?.stats.at(-1);
  const canStop = run && ["created", "starting", "running"].includes(run.status);
  const statusLabel = statusText(run?.status ?? "");

  async function stopRun() {
    setStopping(true);
    try {
      await stopPerformanceRun(projectId, runId);
      await refresh();
      toast.success("已发送停止请求");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setStopping(false);
    }
  }

  if (loading && !run) {
    return <div className="py-16 text-center text-muted-foreground text-sm">正在加载性能测试运行</div>;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-wrap items-center justify-between gap-4 border-y py-5">
        <div>
          <p className="text-muted-foreground text-xs">性能测试运行</p>
          <h1 className="mt-1 font-semibold text-xl">{runId}</h1>
          <div className="mt-2 flex items-center gap-2 text-muted-foreground text-sm">
            <Badge variant={run?.status === "failed" ? "destructive" : "outline"}>{statusLabel}</Badge>
            {run?.error_message ? <span>{run.error_message}</span> : null}
          </div>
        </div>
        <div className="flex gap-2">
          <Button disabled={!canStop || stopping} onClick={stopRun} variant="destructive">
            {stopping ? "停止中" : "停止压测"}
          </Button>
          <Button onClick={() => refresh()} variant="outline">
            刷新
          </Button>
        </div>
      </section>

      <section>
        <SectionTitle title="运行概览" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="当前用户数" value={formatMetric(latest?.user_count)} />
          <Metric label="请求速率" value={formatMetric(latest?.requests_per_second, " RPS")} />
          <Metric label="失败率" value={formatPercent(latest?.failure_rate)} />
          <Metric label="平均响应时间" value={formatMetric(latest?.average_response_time_ms, " ms")} />
          <Metric label="P50" value={formatMetric(latest?.p50_response_time_ms, " ms")} />
          <Metric label="P95" value={formatMetric(latest?.p95_response_time_ms, " ms")} />
          <Metric label="P99" value={formatMetric(latest?.p99_response_time_ms, " ms")} />
          <Metric label="总请求数" value={formatMetric(latest?.request_count)} />
        </div>
      </section>

      <section>
        <SectionTitle title="请求统计" />
        <DataTable
          rows={snapshot?.stats ?? []}
          columns={["sampled_at", "request_count", "failure_count", "requests_per_second", "failure_rate"]}
        />
      </section>

      <section>
        <SectionTitle title="实时图表" />
        <div className="rounded-lg border p-4 text-muted-foreground text-sm">
          当前已接入实时采样数据，图表组件将在采样点达到后展示请求速率、失败率和响应时间趋势。
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div>
          <SectionTitle title="失败请求" />
          <DataTable
            rows={snapshot?.failures ?? []}
            columns={["request_name", "reason", "count", "last_occurred_at"]}
          />
        </div>
        <div>
          <SectionTitle title="异常信息" />
          <DataTable
            rows={snapshot?.exceptions ?? []}
            columns={["request_name", "exception_type", "message", "count"]}
          />
        </div>
      </section>

      <section>
        <SectionTitle title="测试报告" />
        <div className="flex flex-wrap gap-2">
          {(reports?.reports ?? []).map((report) => (
            <a
              className="rounded-md border px-3 py-2 text-sm hover:bg-muted/40"
              href={performanceRunReportUrl(projectId, runId, report.name)}
              key={report.name}
              rel="noreferrer"
              target="_blank"
            >
              下载 {report.name}
            </a>
          ))}
          {!reports?.reports.length ? <span className="text-muted-foreground text-sm">报告尚未生成</span> : null}
        </div>
      </section>

      <section>
        <SectionTitle title="运行日志" />
        <DataTable rows={snapshot?.events ?? []} columns={["created_at", "level", "event_type", "message"]} />
      </section>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="mb-3 font-semibold text-sm">{title}</h2>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-2 font-semibold text-lg">{value}</p>
    </div>
  );
}

function DataTable({ rows, columns }: { rows: Array<Record<string, unknown>>; columns: string[] }) {
  const displayedRows = useMemo(() => rows.slice(-30).reverse(), [rows]);
  return (
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-muted-foreground text-xs">
          <tr>
            {columns.map((column) => (
              <th className="px-3 py-2 font-medium" key={column}>
                {columnLabel(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {displayedRows.length ? (
            displayedRows.map((row) => (
              <tr
                key={String(
                  row.id ??
                    row.sampled_at ??
                    row.created_at ??
                    row.request_name ??
                    row.event_type ??
                    JSON.stringify(row),
                )}
              >
                {columns.map((column) => (
                  <td className="px-3 py-2" key={column}>
                    {String(row[column] ?? "-")}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td className="px-3 py-6 text-center text-muted-foreground" colSpan={columns.length}>
                暂无数据
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function columnLabel(column: string) {
  return (
    {
      sampled_at: "采样时间",
      request_count: "请求数",
      failure_count: "失败数",
      requests_per_second: "RPS",
      failure_rate: "失败率",
      request_name: "请求名称",
      reason: "失败原因",
      count: "次数",
      last_occurred_at: "最近发生",
      exception_type: "异常类型",
      message: "消息",
      created_at: "时间",
      level: "级别",
      event_type: "事件",
    }[column] ?? column
  );
}

function formatMetric(value: unknown, suffix = "") {
  return value === undefined || value === null ? "-" : `${value}${suffix}`;
}

function formatPercent(value: unknown) {
  return value === undefined || value === null ? "-" : `${(Number(value) * 100).toFixed(2)}%`;
}

function statusText(status: string) {
  return (
    {
      created: "已创建",
      starting: "启动中",
      running: "运行中",
      stopping: "停止中",
      completed: "已完成",
      stopped: "已停止",
      failed: "失败",
      cancelled: "已取消",
    }[status] ?? "未知状态"
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "性能测试运行加载失败";
}
