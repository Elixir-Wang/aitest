"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Eye, RefreshCw, Search } from "lucide-react";

import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
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

const modules = ["", "project", "requirement", "system_setting", "model", "task", "auth", "agent"];
const actions = ["", "create", "update", "delete", "merge", "confirm", "cancel", "run", "retry", "export", "login", "logout"];
const results = ["", "success", "failed", "partial_success", "cancelled"];

export function OperationLogView({ endpoint, showProjectFilter = false }: OperationLogViewProps) {
  const [logs, setLogs] = useState<ApiOperationLogListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [module, setModule] = useState("");
  const [action, setAction] = useState("");
  const [result, setResult] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ApiOperationLogDetail | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: "1", page_size: "50" });
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
  }, [action, keyword, module, result]);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<ApiOperationLogList>(`${endpoint}?${query}`);
      setLogs(data.items);
      setTotal(data.total);
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
    try {
      setDetail(await apiRequest<ApiOperationLogDetail>(`/operation-logs/${row.id}`));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "日志详情加载失败");
    }
  }

  return (
    <div className="space-y-4">
      {error ? <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">{error}</div> : null}
      <div className="flex flex-col gap-2 rounded-lg border bg-card p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8" onChange={(event) => setKeyword(event.target.value)} placeholder="搜索对象、摘要或失败原因" value={keyword} />
          </div>
          <NativeSelect aria-label="模块" onChange={(event) => setModule(event.target.value)} value={module}>
            {modules.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogModuleToLabel(item) : "全部模块"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="动作" onChange={(event) => setAction(event.target.value)} value={action}>
            {actions.map((item) => (
              <NativeSelectOption key={item || "all"} value={item}>
                {item ? operationLogActionToLabel(item) : "全部动作"}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <NativeSelect aria-label="结果" onChange={(event) => setResult(event.target.value)} value={result}>
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
              <TableHead className={showProjectFilter ? "w-[18%]" : "w-[22%]"}>对象</TableHead>
              <TableHead className="w-[12%]">操作人</TableHead>
              <TableHead className="w-[10%]">结果</TableHead>
              <TableHead className="w-[20%]">摘要</TableHead>
              <TableHead className="w-[6%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((row) => (
              <TableRow key={row.id}>
                <TableCell className="truncate text-muted-foreground text-xs">{formatDateTime(row.created_at)}</TableCell>
                <TableCell>{operationLogModuleToLabel(row.module)}</TableCell>
                <TableCell>{operationLogActionToLabel(row.action)}</TableCell>
                <TableCell className="truncate" title={row.object_name || row.object_id || ""}>
                  {row.object_name || row.object_id || "-"}
                </TableCell>
                <TableCell className="truncate">{row.actor_name}</TableCell>
                <TableCell>
                  <Badge variant={row.result === "failed" ? "destructive" : "outline"}>{operationLogResultToLabel(row.result)}</Badge>
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
            {loading ? <TableLoadingRow colSpan={8} /> : null}
            {!loading && logs.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                  暂无操作日志。执行创建、编辑、删除或任务操作后，记录会显示在这里。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      <div className="text-muted-foreground text-sm">共 {total} 条日志</div>
      <Drawer direction="right" open={Boolean(selectedId)} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DrawerContent className="sm:max-w-xl">
          <DrawerHeader>
            <DrawerTitle>日志详情</DrawerTitle>
            <DrawerDescription>{detail ? `${operationLogModuleToLabel(detail.module)} / ${operationLogActionToLabel(detail.action)}` : "加载中"}</DrawerDescription>
          </DrawerHeader>
          <div className="space-y-4 overflow-auto px-4 pb-4">
            {detail ? (
              <>
                <DetailGrid detail={detail} />
                <JsonBlock title="变更前" value={detail.before} />
                <JsonBlock title="变更后" value={detail.after} />
                <JsonBlock title="关联产物" value={detail.artifact_path} />
              </>
            ) : (
              <div className="text-muted-foreground text-sm">正在加载日志详情</div>
            )}
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function DetailGrid({ detail }: { detail: ApiOperationLogDetail }) {
  const rows = [
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
    <div className="grid gap-2 rounded-lg border p-3 text-sm">
      {rows.map(([label, value]) => (
        <div className="grid grid-cols-[88px_1fr] gap-3" key={label}>
          <span className="text-muted-foreground">{label}</span>
          <span className="break-words">{value}</span>
        </div>
      ))}
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="space-y-2">
      <h3 className="font-medium text-sm">{title}</h3>
      <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/30 p-3 text-xs">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </div>
  );
}
