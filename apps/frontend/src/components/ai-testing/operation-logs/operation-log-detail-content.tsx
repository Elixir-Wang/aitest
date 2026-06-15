"use client";

import { OneClipboard } from "@/components/ui/one-clipboard";
import { operationLogResultTone, StatusBadge } from "@/components/ui/status-badge";
import { type ApiOperationLogDetail, formatDateTime, operationLogResultToLabel } from "@/lib/api-client";

export function OperationLogDetailContent({ detail }: { detail: ApiOperationLogDetail }) {
  return (
    <>
      <DetailGrid detail={detail} />
      <JsonBlock title="变更前" value={detail.before} />
      <JsonBlock title="变更后" value={detail.after} />
      <JsonBlock title="关联产物" value={detail.artifact_path} />
    </>
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
                <StatusBadge tone={operationLogResultTone(detail.result)}>{value}</StatusBadge>
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
