"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useRouter } from "next/navigation";

import { ArrowRight, Gauge, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, RowActions } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  ApiRequestError,
  deletePerformanceTest,
  formatDateTime,
  listPerformanceTests,
  type PerformanceTest,
} from "@/lib/api-client";

export function PerformanceTestList({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [items, setItems] = useState<PerformanceTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listPerformanceTests(projectId));
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
    return items.filter((item) =>
      [item.name, item.endpoint_name, item.endpoint_method, item.endpoint_path, item.environment_name]
        .join(" ")
        .toLowerCase()
        .includes(keyword),
    );
  }, [items, search]);

  const goalCount = items.filter((item) => Object.keys(item.performance_goal).length > 0).length;
  const failedCount = items.filter(
    (item) => item.latest_run_status === "failed" || item.latest_goal_status === "failed",
  ).length;

  async function remove(item: PerformanceTest) {
    if (!window.confirm(`删除性能测试“${item.name}”？`)) return;
    try {
      await deletePerformanceTest(projectId, item.id);
      toast.success("性能测试已删除");
      await load();
    } catch (error) {
      toast.error(apiErrorMessage(error, "删除失败"));
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid border-y bg-card sm:grid-cols-3">
        <Summary label="性能测试" value={String(items.length)} />
        <Summary label="已配置目标" value={String(goalCount)} />
        <Summary label="最近失败" value={String(failedCount)} warning={failedCount > 0} />
      </div>

      <section className="border-b pb-4">
        <ListToolbar
          createLabel="新建性能测试"
          description="单接口闭合并发模型，认证复用接口自动化环境。"
          onCreate={() => router.push(`/projects/${projectId}/performance-tests/new`)}
          onSearch={setSearch}
          placeholder="搜索名称、接口或环境"
          title="任务定义"
        />

        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>名称</TableHead>
                <TableHead>接口</TableHead>
                <TableHead>环境</TableHead>
                <TableHead>负载</TableHead>
                <TableHead>最近运行</TableHead>
                <TableHead>目标</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell className="h-28 text-center text-muted-foreground" colSpan={8}>
                    正在加载
                  </TableCell>
                </TableRow>
              ) : visibleItems.length === 0 ? (
                <TableRow>
                  <TableCell className="h-40 text-center" colSpan={8}>
                    <div className="flex flex-col items-center gap-3">
                      <Gauge className="size-6 text-muted-foreground" />
                      <div>
                        <p className="font-medium text-sm">暂无性能测试</p>
                        <p className="text-muted-foreground text-xs">从一个已有接口和环境开始。</p>
                      </div>
                      <Button onClick={() => router.push(`/projects/${projectId}/performance-tests/new`)}>
                        新建性能测试
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                visibleItems.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <button
                        className="max-w-56 truncate text-left font-medium hover:underline"
                        onClick={() => router.push(`/projects/${projectId}/performance-tests/${item.id}`)}
                        type="button"
                      >
                        {item.name}
                      </button>
                    </TableCell>
                    <TableCell>
                      {item.endpoint_id ? (
                        <div className="flex max-w-80 items-center gap-2">
                          <MethodBadge method={item.endpoint_method} />
                          <span className="truncate font-mono text-xs" title={item.endpoint_path}>
                            {item.endpoint_path}
                          </span>
                        </div>
                      ) : (
                        <Badge variant="destructive">引用已失效</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {item.api_environment_id ? (
                        item.environment_name
                      ) : (
                        <Badge variant="destructive">引用已失效</Badge>
                      )}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {item.load_config.users} 用户 / {item.load_config.spawn_rate}/秒
                    </TableCell>
                    <TableCell>
                      <RunBadge status={item.latest_run_status} />
                    </TableCell>
                    <TableCell>
                      <GoalBadge
                        status={item.latest_goal_status}
                        configured={Object.keys(item.performance_goal).length > 0}
                      />
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-muted-foreground text-xs">
                      {formatDateTime(item.updated_at)}
                    </TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          {
                            label: "查看",
                            icon: ArrowRight,
                            href: `/projects/${projectId}/performance-tests/${item.id}`,
                          },
                          { label: "删除", icon: Trash2, destructive: true, onSelect: () => void remove(item) },
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
      </section>
    </div>
  );
}

function Summary({ label, value, warning = false }: { label: string; value: string; warning?: boolean }) {
  return (
    <div className="border-b px-4 py-3 last:border-b-0 sm:border-r sm:border-b-0 sm:last:border-r-0">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className={warning ? "mt-1 font-semibold text-destructive text-lg" : "mt-1 font-semibold text-lg"}>{value}</p>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  return (
    <span className="rounded-md bg-sky-100 px-1.5 py-0.5 font-bold text-[11px] text-sky-700 dark:bg-sky-950 dark:text-sky-300">
      {method || "-"}
    </span>
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

function GoalBadge({ status, configured }: { status: string; configured: boolean }) {
  if (!configured) return <Badge variant="outline">未配置</Badge>;
  if (!status) return <Badge variant="outline">待评估</Badge>;
  const label = { passed: "通过", failed: "未通过", not_evaluated: "未评估" }[status] ?? status;
  return <Badge variant={status === "failed" ? "destructive" : "secondary"}>{label}</Badge>;
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) {
    return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  }
  return fallback;
}
