"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { FileCode2, Gauge, Loader2, Pencil, SquareTerminal, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ApiRequestError,
  deletePerformanceTest,
  ensurePerformanceRun,
  formatDateTime,
  listPerformanceTests,
  type PerformanceTest,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

export function PerformanceTestList({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<PerformanceTest[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [consoleItemId, setConsoleItemId] = useState<string | null>(null);
  const [pendingDeleteIds, setPendingDeleteIds] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listPerformanceTests(projectId);
      setItems(rows);
      setSelectedIds((current) => current.filter((id) => rows.some((item) => item.id === id)));
    } catch (error) {
      toast.error(apiErrorMessage(error, "性能测试加载失败"));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return items;
    return items.filter((item) => [item.name, item.environment_name].join(" ").toLowerCase().includes(keyword));
  }, [items, search]);

  const visibleIds = visibleItems.map((item) => item.id);
  const visibleSelectedIds = visibleIds.filter((id) => selectedIds.includes(id));
  const allSelected = visibleIds.length > 0 && visibleSelectedIds.length === visibleIds.length;
  const partiallySelected = visibleSelectedIds.length > 0 && !allSelected;

  function toggleOne(itemId: string, checked: boolean) {
    setSelectedIds((current) => (checked ? [...new Set([...current, itemId])] : current.filter((id) => id !== itemId)));
  }

  function toggleAll(checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...new Set([...current, ...visibleIds])] : current.filter((id) => !visibleIds.includes(id)),
    );
  }

  function requestRemoveItems(ids: string[]) {
    if (ids.length === 0) return;
    setPendingDeleteIds(ids);
  }

  async function removeItems() {
    if (pendingDeleteIds.length === 0) return;
    setBusy(true);
    try {
      await Promise.all(pendingDeleteIds.map((id) => deletePerformanceTest(projectId, id)));
      setSelectedIds([]);
      await load();
      toast.success(`已删除 ${pendingDeleteIds.length} 个性能测试`);
      setPendingDeleteIds([]);
    } catch (error) {
      toast.error(apiErrorMessage(error, "删除失败"));
    } finally {
      setBusy(false);
    }
  }

  async function enterConsole(item: PerformanceTest) {
    if (!item.latest_script_id) return;
    setConsoleItemId(item.id);
    try {
      if (item.latest_run_id) {
        router.push(`/projects/${projectId}/performance-tests/${item.id}/runs/${item.latest_run_id}`);
        return;
      }
      const run = await ensurePerformanceRun(projectId, item.id, item.latest_script_id);
      router.push(`/projects/${projectId}/performance-tests/${item.id}/runs/${run.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "进入控制台失败"));
    } finally {
      setConsoleItemId(null);
    }
  }

  return (
    <ShellSection>
      <ListToolbar
        createLabel="新建性能测试"
        description=""
        onBatchDelete={
          busy || visibleSelectedIds.length === 0 ? undefined : () => requestRemoveItems(visibleSelectedIds)
        }
        onCreate={() => router.push("/performance-tests/new")}
        onSearch={setSearch}
        placeholder="搜索名称或环境"
        selectedCount={visibleSelectedIds.length}
        title="任务列表"
      />

      <div className="overflow-hidden rounded-lg border">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[5%]">
                <Checkbox
                  aria-label="选择全部性能测试"
                  checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                  disabled={busy || loading}
                  onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                />
              </TableHead>
              <TableHead className="w-[25%]">名称</TableHead>
              <TableHead className="w-[18%]">环境</TableHead>
              <TableHead className="w-[15%]">测试模式</TableHead>
              <TableHead className="w-[12%]">状态</TableHead>
              <TableHead className="w-[10%]">更新时间</TableHead>
              <TableHead className="w-[7%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visibleItems.map((item) => (
              <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                <TableCell>
                  <Checkbox
                    aria-label={`选择 ${item.name}`}
                    checked={selectedIds.includes(item.id)}
                    disabled={busy}
                    onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                  />
                </TableCell>
                <TableCell>
                  <button
                    className="max-w-48 truncate text-left font-medium hover:underline"
                    onClick={() => {
                      if (item.latest_script_id) {
                        router.push(
                          `/projects/${projectId}/performance-tests/${item.id}/scripts/${item.latest_script_id}`,
                        );
                      } else {
                        router.push(`/projects/${projectId}/performance-tests`);
                      }
                    }}
                    title={item.name}
                    type="button"
                  >
                    {item.name}
                  </button>
                </TableCell>
                <TableCell>
                  {item.api_environment_id ? item.environment_name : <Badge variant="destructive">引用已失效</Badge>}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{getModeLabel(item.load_config.mode)}</Badge>
                </TableCell>
                <TableCell>
                  <RunBadge status={item.latest_run_status} />
                </TableCell>
                <TableCell className="text-muted-foreground">{formatDateTime(item.updated_at)}</TableCell>
                <TableCell>
                  <RowActions
                    actions={[
                      {
                        label: "查看脚本",
                        icon: FileCode2,
                        disabled: !item.latest_script_id,
                        onSelect: item.latest_script_id
                          ? () =>
                              router.push(
                                `/projects/${projectId}/performance-tests/${item.id}/scripts/${item.latest_script_id}`,
                              )
                          : undefined,
                      },
                      {
                        label: "编辑",

                        icon: Pencil,

                        onSelect: () => router.push(`/projects/${projectId}/performance-tests/${item.id}/edit`),
                      },

                      {
                        label: "进入控制台",
                        icon: SquareTerminal,
                        disabled: busy || consoleItemId === item.id || !item.latest_script_id,
                        onSelect: () => void enterConsole(item),
                      },
                      {
                        label: "删除",
                        icon: Trash2,
                        destructive: true,
                        disabled: busy,
                        onSelect: busy ? undefined : () => requestRemoveItems([item.id]),
                      },
                    ]}
                    label={`${item.name} 操作`}
                  />
                </TableCell>
              </TableRow>
            ))}
            {loading && visibleItems.length === 0 ? <TableLoadingRow colSpan={7} label="性能测试加载中" /> : null}
            {!loading && visibleItems.length === 0 ? (
              <TableRow>
                <TableCell className="h-40 text-center" colSpan={7}>
                  <div className="flex flex-col items-center gap-3">
                    <Gauge className="size-6 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">暂无性能测试</p>
                      <p className="text-muted-foreground text-xs">从一个已有接口和环境开始。</p>
                    </div>
                    <Button onClick={() => router.push("/performance-tests/new")}>新建性能测试</Button>
                  </div>
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>
      <AlertDialog
        onOpenChange={(open) => !busy && !open && setPendingDeleteIds([])}
        open={pendingDeleteIds.length > 0}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <div className="flex size-10 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
              <Trash2 className="size-5" />
            </div>
            <AlertDialogTitle>删除性能测试？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后将同时删除该条目下的全部压测历史、趋势、日志和下载文件，且无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={busy}
              onClick={(event) => {
                event.preventDefault();
                void removeItems();
              }}
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              {busy ? "删除中" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ShellSection>
  );
}

function RunBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    created: "就绪",
    starting: "启动中",
    ready: "就绪",
    queued: "排队中",
    preparing: "准备中",
    running: "运行中",
    stopping: "停止中",
    completed: "已完成",
    stopped: "已停止",
    failed: "失败",
    cancelled: "已取消",
    interrupted: "已中断",
  };
  if (!status) return <Badge variant="outline">未运行</Badge>;
  return <Badge variant="outline">{labels[status] ?? "未知状态"}</Badge>;
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) {
    return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  }
  return fallback;
}

function getModeLabel(mode: string) {
  const labels: Record<string, string> = {
    fixed: "固定负载",
    gradient: "手动梯度",
    stress: "压力测试",
    spike: "峰值测试",
    endurance: "耐久测试",
  };
  return labels[mode] ?? mode;
}
