"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { List, Loader2, Network, Pencil, RefreshCw, Save, X } from "lucide-react";
import { createPortal } from "react-dom";
import { toast } from "sonner";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { ListToolbar, ShellSection } from "@/components/ai-testing/page-shell";
import { StandardMarkdownEditor } from "@/components/ai-testing/standard-markdown-editor";
import { TestPointCoverageSummary } from "@/components/ai-testing/test-point-coverage-summary";
import { TestPointMindMap } from "@/components/ai-testing/test-point-mind-map";
import { TestPointsList } from "@/components/ai-testing/test-points-list";
import { AiEditInput } from "@/components/ui/ai-input";
import { Button } from "@/components/ui/button";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { ApiRequestError, type ApiTestPointOverview, apiRequest, generateTestPoints } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

type DocumentEditResponse = {
  edited_content: string;
  change_summary: string;
};

export function TestPointsPanel({
  projectId,
  documentId,
  canEdit,
  onOverviewChange,
  actionContainer,
}: {
  projectId: string;
  documentId: string;
  canEdit: boolean;
  onOverviewChange?: (overview: ApiTestPointOverview) => void;
  actionContainer?: HTMLElement | null;
}) {
  const [data, setData] = useState<ApiTestPointOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingWithAi, setEditingWithAi] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "mindmap">("list");
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const mindMapContainerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        setError("");
        const overview = await apiRequest<ApiTestPointOverview>(
          `/projects/${projectId}/requirements/${documentId}/test-points`,
        );
        setData(overview);
        onOverviewChange?.(overview);
        setMarkdownDraft(overview.markdown_content);
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
    [documentId, onOverviewChange, projectId],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!data?.run || !ACTIVE_STATUSES.has(data.run.status)) return;
    const timer = window.setInterval(() => void load(true), 2500);
    return () => window.clearInterval(timer);
  }, [data?.run, load]);

  useEffect(() => {
    if (viewMode !== "mindmap") return;

    const resizeMindMapContainer = () => {
      const container = mindMapContainerRef.current;
      if (!container) return;
      const availableHeight = window.innerHeight - container.getBoundingClientRect().top - 16;
      container.style.height = `${Math.max(512, availableHeight)}px`;
    };

    const frameId = window.requestAnimationFrame(resizeMindMapContainer);
    window.addEventListener("resize", resizeMindMapContainer);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener("resize", resizeMindMapContainer);
    };
  }, [viewMode]);

  async function persistMarkdown(markdownContent: string) {
    const updated = await apiRequest<ApiTestPointOverview>(
      `/projects/${projectId}/requirements/${documentId}/test-points/markdown`,
      {
        method: "PUT",
        body: JSON.stringify({ markdown_content: markdownContent }),
      },
    );
    setData(updated);
    setMarkdownDraft(updated.markdown_content);
    setEditing(false);
    return updated;
  }

  async function saveMarkdownDraft() {
    setSaving(true);
    try {
      await persistMarkdown(markdownDraft);
      toast.success("测试点已保存");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试点保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function editTestPointsWithAi(instruction: string) {
    if (!data?.markdown_content.trim()) return;
    setEditingWithAi(true);
    let editedContent = "";
    try {
      const editResult = await apiRequest<DocumentEditResponse>("/agents/document-editor/run", {
        method: "POST",
        body: JSON.stringify({ content: data.markdown_content, instruction }),
      });
      editedContent = editResult.edited_content;
      if (!editedContent.trim()) {
        toast.info(editResult.change_summary || "AI 未修改测试点");
        return;
      }
      await persistMarkdown(editedContent);
      toast.success(editResult.change_summary || "AI修改已保存");
    } catch (requestError) {
      if (editedContent.trim()) {
        setMarkdownDraft(editedContent);
        setEditing(true);
      }
      toast.error(requestError instanceof Error ? requestError.message : "智能修改失败");
    } finally {
      setEditingWithAi(false);
    }
  }

  async function regenerateTestPoints() {
    if (!data?.requirement_version_id) return;
    setRegenerating(true);
    try {
      const run = await generateTestPoints(projectId, documentId);
      setData((current) =>
        current
          ? {
              ...current,
              run,
              points: [],
              markdown_content: "",
              coverage_summary: {
                status: "pending",
                obligation_count: 0,
                covered_obligation_count: 0,
                missing_obligations: [],
                unsupported_assumptions: [],
                supplement_round: 0,
              },
            }
          : current,
      );
      setMarkdownDraft("");
      setEditing(false);
      setSelectedPointId(null);
      toast.success(hasPoints ? "测试点正在重新生成中..." : "测试点正在生成中...");
      notifyAiTaskStarted();
      void load(true);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "重新生成失败");
    } finally {
      setRegenerating(false);
    }
  }

  const isRunning = Boolean(data?.run && ACTIVE_STATUSES.has(data.run.status));
  const hasPoints = Boolean(data?.points.length);
  const showActions = Boolean(canEdit && hasPoints && !isRunning && !regenerating);

  const filteredPoints = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return data?.points ?? [];
    return (data?.points ?? []).filter(
      (p) =>
        p.title.toLowerCase().includes(keyword) ||
        p.module?.toLowerCase().includes(keyword) ||
        p.priority.toLowerCase().includes(keyword),
    );
  }, [data?.points, search]);

  function handleSelectPoint(pointId: string) {
    setSelectedPointId(pointId);
  }

  async function handleEditPoint(pointId: string, title: string) {
    try {
      await apiRequest(`/projects/${projectId}/requirements/${documentId}/test-points/${pointId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setData((current) =>
        current
          ? {
              ...current,
              points: current.points.map((point) => (point.id === pointId ? { ...point, title } : point)),
            }
          : current,
      );
      await load(true);
      toast.success("测试要点已更新");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试要点更新失败");
      throw requestError;
    }
  }

  const testPointActions = data?.requirement_version_id ? (
    <>
      {hasPoints ? (
        <fieldset aria-label="视图切换" className="flex h-8 rounded-lg border bg-slate-50 p-0.5 dark:bg-muted/50">
          <Button
            className="h-full gap-1.5 px-3 text-sm"
            onClick={() => setViewMode("list")}
            size="sm"
            variant={viewMode === "list" ? "secondary" : "ghost"}
          >
            <List className="size-4" />
            列表
          </Button>
          <Button
            className="h-full gap-1.5 px-3 text-sm"
            onClick={() => setViewMode("mindmap")}
            size="sm"
            variant={viewMode === "mindmap" ? "secondary" : "ghost"}
          >
            <Network className="size-4" />
            脑图
          </Button>
        </fieldset>
      ) : null}
      {showActions ? (
        <>
          <Button
            disabled={regenerating || isRunning}
            onClick={regenerateTestPoints}
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCw className={cn("size-3.5", regenerating && "animate-spin")} />
            {regenerating ? "重新生成中" : "重新生成"}
          </Button>
          {editing ? (
            <>
              <Button disabled={saving} onClick={saveMarkdownDraft} size="sm" type="button">
                <Save className="size-3.5" />
                {saving ? "保存中" : "保存"}
              </Button>
              <Button
                disabled={saving}
                onClick={() => {
                  setMarkdownDraft(data?.markdown_content ?? "");
                  setEditing(false);
                }}
                size="sm"
                type="button"
                variant="outline"
              >
                <X className="size-3.5" />
                取消
              </Button>
            </>
          ) : (
            <>
              <AiEditInput
                disabled={editingWithAi}
                loading={editingWithAi}
                onSubmit={editTestPointsWithAi}
                placeholder="描述你希望如何修改当前测试点..."
                title="AI修改测试点"
              />
              <Button
                onClick={() => {
                  setMarkdownDraft(data?.markdown_content ?? "");
                  setEditing(true);
                }}
                size="sm"
                type="button"
                variant="outline"
              >
                <Pencil className="size-3.5" />
                修改
              </Button>
            </>
          )}
        </>
      ) : !hasPoints && canEdit ? (
        <Button disabled={regenerating || isRunning} onClick={regenerateTestPoints} size="sm" type="button">
          <RefreshCw className={cn("size-3.5", (regenerating || isRunning) && "animate-spin")} />
          {regenerating || isRunning ? "生成中" : "生成测试点"}
        </Button>
      ) : null}
    </>
  ) : null;

  return (
    <div>
      {loading ? (
        <div className="flex items-center gap-2 p-6 text-muted-foreground text-sm">
          <Loader2 className="size-4 animate-spin" />
          加载测试点中...
        </div>
      ) : error ? (
        <div className="p-6 text-destructive text-sm">{error}</div>
      ) : !data?.requirement_version_id ? (
        <IllustratedEmptyState
          className="rounded-lg border border-dashed bg-muted/10"
          description="请先在需求分析中点击“转为最终需求”。"
          title="暂无测试点"
        />
      ) : (
        <div className="space-y-4">
          <TestPointCoverageSummary coverage={data.coverage_summary} />
          {!hasPoints ? (
            <IllustratedEmptyState
              className="rounded-lg border border-dashed bg-muted/10"
              description="当前最终需求尚未生成测试点。"
              title="暂无测试点"
            />
          ) : null}
          {hasPoints ? (
            <ShellSection>
              <ListToolbar onSearch={setSearch} placeholder="搜索测试点标题、模块或优先级" title="测试点列表" />
              {editing ? (
                <StandardMarkdownEditor content={markdownDraft} onChange={setMarkdownDraft} />
              ) : viewMode === "mindmap" ? (
                <div className="flex min-h-[32rem] flex-none rounded-lg border" ref={mindMapContainerRef}>
                  <TestPointMindMap
                    active={true}
                    editable={canEdit}
                    points={filteredPoints}
                    selectedPointId={selectedPointId}
                    onEditPoint={handleEditPoint}
                    onSelectPoint={handleSelectPoint}
                  />
                </div>
              ) : (
                <TestPointsList
                  projectId={projectId}
                  documentId={documentId}
                  data={data}
                  canEdit={Boolean(canEdit)}
                  key={search}
                  search={search}
                  onDataChange={() => void load(true)}
                  highlightedId={selectedPointId}
                />
              )}
            </ShellSection>
          ) : null}
        </div>
      )}
      {actionContainer && testPointActions ? createPortal(testPointActions, actionContainer) : null}
    </div>
  );
}
