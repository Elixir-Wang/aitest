"use client";

import { useCallback, useEffect, useState } from "react";

import { Loader2, Pencil, RefreshCw, Save, X } from "lucide-react";
import { toast } from "sonner";

import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { ListToolbar, ShellSection } from "@/components/ai-testing/page-shell";
import { StandardMarkdownEditor } from "@/components/ai-testing/standard-markdown-editor";
import { TestPointsList } from "@/components/ai-testing/test-points-list";
import { AiEditInput } from "@/components/ui/ai-input";
import { Button } from "@/components/ui/button";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { ApiRequestError, type ApiTestPointOverview, apiRequest, generateTestPoints } from "@/lib/api-client";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

type DocumentEditResponse = {
  edited_content: string;
  change_summary: string;
};

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
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingWithAi, setEditingWithAi] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        setError("");
        const overview = await apiRequest<ApiTestPointOverview>(
          `/projects/${projectId}/requirements/${documentId}/test-points`,
        );
        setData(overview);
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
      await generateTestPoints(projectId, documentId);
      toast.success("测试点正在重新生成中...");
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
          {data.run?.status === "failed" ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
              {data.run.error_message || "测试点生成失败"}
            </div>
          ) : null}
          {!hasPoints ? (
            <IllustratedEmptyState
              className="rounded-lg border border-dashed bg-muted/10"
              description="当前最终需求尚未生成测试点。"
              title="暂无测试点"
            />
          ) : null}
          {hasPoints ? (
            <ShellSection>
              <ListToolbar
                actions={
                  showActions ? (
                    <>
                      {data.requirement_version_id ? (
                        <Button
                          disabled={regenerating || isRunning}
                          onClick={regenerateTestPoints}
                          size="sm"
                          type="button"
                          variant="outline"
                        >
                          <RefreshCw className={`size-3.5 ${regenerating ? "animate-spin" : ""}`} />
                          {regenerating ? "重新生成中" : "重新生成"}
                        </Button>
                      ) : null}
                      {editing ? (
                        <>
                          <Button disabled={saving} onClick={saveMarkdownDraft} size="sm" type="button">
                            <Save className="size-3.5" />
                            {saving ? "保存中" : "保存"}
                          </Button>
                          <Button
                            disabled={saving}
                            onClick={() => {
                              setMarkdownDraft(data.markdown_content ?? "");
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
                              setMarkdownDraft(data.markdown_content ?? "");
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
                  ) : null
                }
                onSearch={setSearch}
                placeholder="搜索测试点标题、模块或类型"
                title="测试点列表"
              />
              {editing ? (
                <StandardMarkdownEditor content={markdownDraft} onChange={setMarkdownDraft} />
              ) : (
                <TestPointsList
                  projectId={projectId}
                  documentId={documentId}
                  data={data}
                  canEdit={Boolean(canEdit)}
                  key={search}
                  search={search}
                  onDataChange={() => void load(true)}
                />
              )}
            </ShellSection>
          ) : null}
        </div>
      )}
    </div>
  );
}
