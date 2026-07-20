"use client";

import { useCallback, useEffect, useState } from "react";

import { Check, Loader2, Play, Save } from "lucide-react";
import { toast } from "sonner";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, type ApiTestPoint, type ApiTestPointOverview, apiRequest } from "@/lib/api-client";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export function TestPointsPanel({
  projectId,
  documentId,
  canEdit,
}: {
  projectId: string;
  documentId: string;
  canEdit: boolean;
}) {
  const [data, setData] = useState<ApiTestPointOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState("");

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        setError("");
        setData(
          await apiRequest<ApiTestPointOverview>(`/projects/${projectId}/requirements/${documentId}/test-points`),
        );
      } catch (requestError) {
        setError(
          requestError instanceof ApiRequestError && requestError.status === 404
            ? "测试点服务尚未加载，请重启后端服务后刷新页面。"
            : requestError instanceof Error
              ? requestError.message
              : "测试点加载失败",
        );
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [documentId, projectId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!data?.run || !ACTIVE_STATUSES.has(data.run.status)) return;
    const timer = window.setInterval(() => void load(true), 2500);
    return () => window.clearInterval(timer);
  }, [data?.run, load]);

  async function generate() {
    try {
      const run = await apiRequest<ApiTestPointOverview["run"]>(
        `/projects/${projectId}/requirements/${documentId}/test-points/generate`,
        { method: "POST" },
      );
      setData((current) => (current ? { ...current, run } : current));
      toast.success("测试点生成任务已提交");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "提交测试点生成失败");
    }
  }

  async function save(point: ApiTestPoint) {
    setSavingId(point.id);
    try {
      const updated = await apiRequest<ApiTestPoint>(
        `/projects/${projectId}/requirements/${documentId}/test-points/${point.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({ title: point.title, description: point.description, status: point.status }),
        },
      );
      setData((current) =>
        current
          ? { ...current, points: current.points.map((item) => (item.id === updated.id ? updated : item)) }
          : current,
      );
      toast.success("测试点已保存");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试点保存失败");
    } finally {
      setSavingId("");
    }
  }

  function updatePoint(id: string, patch: Partial<ApiTestPoint>) {
    setData((current) =>
      current
        ? { ...current, points: current.points.map((item) => (item.id === id ? { ...item, ...patch } : item)) }
        : current,
    );
  }

  if (loading)
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground text-sm">
        <Loader2 className="size-4 animate-spin" />
        加载测试点中...
      </div>
    );
  if (error) return <div className="p-6 text-destructive text-sm">{error}</div>;
  if (!data?.requirement_version_id)
    return (
      <IllustratedEmptyState
        className="rounded-lg border border-dashed bg-muted/10"
        description="请先在需求分析中点击“转为最终需求”。"
        title="暂无测试点"
      />
    );

  const isRunning = Boolean(data.run && ACTIVE_STATUSES.has(data.run.status));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-muted-foreground text-sm">
          最终需求 v{data.requirement_version_no} · {data.points.length} 个测试点
        </div>
        {canEdit ? (
          <Button disabled={isRunning} onClick={generate} type="button">
            <Play className="size-4" />
            {isRunning ? "生成中" : "重新生成测试点"}
          </Button>
        ) : null}
      </div>
      {data.run?.status === "failed" ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
          {data.run.error_message || "测试点生成失败"}
        </div>
      ) : null}
      {data.points.length === 0 && !isRunning ? (
        <IllustratedEmptyState
          action={
            canEdit ? (
              <Button onClick={generate} size="sm" type="button">
                <Play className="size-4" />
                生成测试点
              </Button>
            ) : null
          }
          className="rounded-lg border border-dashed bg-muted/10"
          description="当前最终需求尚未生成测试点。"
          title="暂无测试点"
        />
      ) : null}
      {data.points.length > 0 ? (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>测试点</TableHead>
                <TableHead>模块</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>优先级</TableHead>
                <TableHead>验证点</TableHead>
                <TableHead>状态</TableHead>
                <TableHead className="w-20">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.points.map((point) => (
                <TableRow key={point.id}>
                  <TableCell className="align-top">
                    <Input
                      disabled={!canEdit}
                      onChange={(event) => updatePoint(point.id, { title: event.target.value })}
                      value={point.title}
                    />
                    <div className="mt-1 text-muted-foreground text-xs">{point.point_key}</div>
                    <Textarea
                      className="mt-2 min-h-16"
                      disabled={!canEdit}
                      onChange={(event) => updatePoint(point.id, { description: event.target.value })}
                      value={point.description}
                    />
                  </TableCell>
                  <TableCell className="align-top">{point.module || "-"}</TableCell>
                  <TableCell className="align-top">{point.category}</TableCell>
                  <TableCell className="align-top">{point.priority}</TableCell>
                  <TableCell className="align-top text-xs">
                    {point.verification_points.map((item) => (
                      <div key={item} className="mb-1">
                        • {item}
                      </div>
                    ))}
                  </TableCell>
                  <TableCell className="align-top">
                    <Button
                      disabled={!canEdit}
                      onClick={() =>
                        updatePoint(point.id, { status: point.status === "confirmed" ? "draft" : "confirmed" })
                      }
                      size="sm"
                      type="button"
                      variant={point.status === "confirmed" ? "default" : "outline"}
                    >
                      {point.status === "confirmed" ? <Check className="size-4" /> : null}
                      {point.status === "confirmed" ? "已确认" : "草稿"}
                    </Button>
                  </TableCell>
                  <TableCell className="align-top">
                    <Button
                      disabled={!canEdit || savingId === point.id}
                      onClick={() => void save(point)}
                      size="icon"
                      title="保存测试点"
                      type="button"
                      variant="ghost"
                    >
                      {savingId === point.id ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Save className="size-4" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  );
}
