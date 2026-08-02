"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { ArrowRight, Eye, Gauge, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ApiRequestError,
  deletePerformanceTest,
  formatDateTime,
  listPerformanceTests,
  type PerformanceTest,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { PerformanceTestParamsDialog } from "./performance-test-params-dialog";

export function PerformanceTestList({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<PerformanceTest[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [paramsItem, setParamsItem] = useState<PerformanceTest | null>(null);

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

  async function removeItems(ids: string[]) {
    if (ids.length === 0) return;
    if (!window.confirm("删除后将同时删除该条目下的全部压测历史、趋势、日志和下载文件，且无法恢复。")) return;
    setBusy(true);
    try {
      await Promise.all(ids.map((id) => deletePerformanceTest(projectId, id)));
      setSelectedIds([]);
      await load();
      toast.success(`已删除 ${ids.length} 个性能测试`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "删除失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ShellSection>
      <ListToolbar
        createLabel="新建性能测试"
        description=""
        onBatchDelete={busy || visibleSelectedIds.length === 0 ? undefined : () => removeItems(visibleSelectedIds)}
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
              <TableHead className="w-[5%]" />
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
                        label: "查看参数",
                        icon: Eye,
                        onSelect: () => setParamsItem(item),
                      },
                      {
                        label: "脚本审核",
                        icon: ArrowRight,
                        href: item.latest_script_id
                          ? `/projects/${projectId}/performance-tests/${item.id}/scripts/${item.latest_script_id}`
                          : `/projects/${projectId}/performance-tests`,
                      },
                      {
                        label: "删除",
                        icon: Trash2,
                        destructive: true,
                        disabled: busy,
                        onSelect: busy ? undefined : () => removeItems([item.id]),
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
      <PerformanceTestParamsDialog item={paramsItem} onOpenChange={(open) => !open && setParamsItem(null)} />
    </ShellSection>
  );
}

function RunBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    queued: "排队中",
    preparing: "准备中",
    running: "运行中",
    stopping: "停止中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
    interrupted: "已中断",
  };
  if (!status) return <Badge variant="outline">未运行</Badge>;
  return (
    <Badge variant={status === "failed" ? "destructive" : status === "completed" ? "secondary" : "outline"}>
      {labels[status] ?? status}
    </Badge>
  );
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
