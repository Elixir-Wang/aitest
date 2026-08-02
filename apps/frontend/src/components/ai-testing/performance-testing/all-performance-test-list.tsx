"use client";

import { useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { ArrowRight, Eye, Gauge, Plus, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiProject,
  ApiRequestError,
  apiRequest,
  deletePerformanceTest,
  formatDateTime,
  listPerformanceTests,
  type PerformanceTest,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { PerformanceTestParamsDialog } from "./performance-test-params-dialog";

type ProjectPerformanceTest = PerformanceTest & { projectId: string; projectName: string };

export function AllPerformanceTestList() {
  const router = useRouter();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [items, setItems] = useState<ProjectPerformanceTest[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [paramsItem, setParamsItem] = useState<PerformanceTest | null>(null);

  const itemProjectIdMap = useMemo(() => {
    const map: Record<string, string> = {};
    for (const item of items) {
      map[item.id] = item.projectId;
    }
    return map;
  }, [items]);

  useEffect(() => {
    let ignore = false;
    apiRequest<ApiProject[]>("/projects")
      .then(async (projects) => {
        if (!ignore) setProjects(projects.filter((project) => project.status === "active"));
        const rows = await Promise.all(
          projects.map(async (project) =>
            (await listPerformanceTests(project.id)).map((item) => ({
              ...item,
              projectId: project.id,
              projectName: project.name,
            })),
          ),
        );
        if (!ignore) setItems(rows.flat());
      })
      .catch((error) => toast.error(apiErrorMessage(error)))
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const visibleItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return keyword
      ? items.filter((item) =>
          [item.name, item.projectName, item.environment_name].join(" ").toLowerCase().includes(keyword),
        )
      : items;
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
      await Promise.all(ids.map((id) => deletePerformanceTest(itemProjectIdMap[id], id)));
      setSelectedIds([]);
      await refreshItems();
      toast.success(`已删除 ${ids.length} 个性能测试`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "删除失败"));
    } finally {
      setBusy(false);
    }
  }

  async function refreshItems() {
    setLoading(true);
    try {
      const rows = await Promise.all(
        projects.map(async (project) =>
          (await listPerformanceTests(project.id)).map((item) => ({
            ...item,
            projectId: project.id,
            projectName: project.name,
          })),
        ),
      );
      setItems(rows.flat());
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  function createPerformanceTest() {
    router.push("/performance-tests/new");
  }

  return (
    <ShellSection>
      <ListToolbar
        actions={
          <Button disabled={loading || projects.length === 0} onClick={createPerformanceTest}>
            <Plus className="size-4" />
            新建性能测试
          </Button>
        }
        description=""
        onBatchDelete={busy || visibleSelectedIds.length === 0 ? undefined : () => removeItems(visibleSelectedIds)}
        onSearch={setSearch}
        placeholder="搜索项目、名称或环境"
        selectedCount={visibleSelectedIds.length}
        title="性能测试列表"
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
              <TableHead className="w-[20%]">名称</TableHead>
              <TableHead className="w-[18%]">环境</TableHead>
              <TableHead className="w-[15%]">测试模式</TableHead>
              <TableHead className="w-[12%]">状态</TableHead>
              <TableHead className="w-[12%]">更新时间</TableHead>
              <TableHead className="w-[5%]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading || visibleItems.length === 0 ? (
              <TableRow>
                <TableCell className="h-40 text-center" colSpan={7}>
                  <div className="flex flex-col items-center gap-3">
                    <Gauge className="size-6 text-muted-foreground" />
                    <div>
                      <p className="font-medium text-sm">{loading ? "正在加载" : "暂无性能测试"}</p>
                      {!loading ? (
                        <p className="mt-1 text-muted-foreground text-xs">新建第一个性能测试并选择目标项目。</p>
                      ) : null}
                    </div>
                    {!loading && projects.length > 0 ? (
                      <Button onClick={createPerformanceTest} size="sm">
                        <Plus className="size-4" />
                        新建性能测试
                      </Button>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              visibleItems.map((item) => (
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
                    <Link
                      className="block max-w-48 truncate font-medium hover:underline"
                      href={
                        item.latest_script_id
                          ? `/projects/${item.projectId}/performance-tests/${item.id}/scripts/${item.latest_script_id}`
                          : `/projects/${item.projectId}/performance-tests`
                      }
                      title={item.name}
                    >
                      {item.name}
                    </Link>
                  </TableCell>
                  <TableCell className="truncate" title={item.environment_name}>
                    {item.api_environment_id ? item.environment_name : "引用已失效"}
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
                            ? `/projects/${item.projectId}/performance-tests/${item.id}/scripts/${item.latest_script_id}`
                            : `/projects/${item.projectId}/performance-tests`,
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
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <PerformanceTestParamsDialog item={paramsItem} onOpenChange={(open) => !open && setParamsItem(null)} />
    </ShellSection>
  );
}

function apiErrorMessage(error: unknown, fallback?: string) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return fallback ?? "性能测试加载失败";
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
