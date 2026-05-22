"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, Check, FilePlus2, GitMerge, Pencil, Save, X } from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import {
  RequirementFileSwitcher,
  type RequirementSwitcherFile,
} from "@/components/ai-testing/requirement-file-switcher";
import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, formatDateTime } from "@/lib/api-client";

type RequirementConflict = {
  id: string;
  title: string;
  source_file_names: string;
  fragment_a: string;
  fragment_b: string;
  resolution: string;
  resolution_type: string;
  status: string;
};

type SourceFile = RequirementSwitcherFile & {
  version_id: string | null;
  version_no: number | null;
  markdown_file_path: string | null;
  conversion_summary: string;
  standard_file_status?: string;
  conflict_status?: string;
};

type RequirementOverviewResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    document_type: string;
    status: string;
    updated_at: string;
    current_version_id: string | null;
  };
  stats: {
    total_files: number;
    conversion_success: number;
    conversion_warning: number;
    conversion_failed: number;
    mergeable_files: number;
    open_conflicts: number;
    initial_requirement_status: string;
  };
  files: SourceFile[];
  has_open_conflicts: boolean;
  initial_markdown_content: string;
};

type OriginalPreview = {
  title: string;
  fileFormat: string;
  contentType: "text" | "download";
  content: string;
};

type StandardPreview = {
  title: string;
  markdownContent: string;
  conversionSummary: string;
};

type MergeResponse =
  | {
      status: "merged";
      version_id: string;
      version_no: number;
      markdown_content: string;
      merge_summary: string;
      source_file_ids: string[];
    }
  | {
      status: "conflict";
      conflict_count: number;
      conflicts: RequirementConflict[];
    };

const conversionLabels: Record<string, string> = {
  pending: "待转换",
  processing: "转换中",
  success: "转换成功",
  warning: "有警告",
  failed: "转换失败",
};

const mappingLabels: Record<string, string> = {
  pending_merge: "待归并",
  pending_review: "待评审",
  merged: "已归并",
  discarded: "已废弃",
};

const standardFileLabels: Record<string, string> = {
  not_generated: "未生成",
  ready: "可合并",
  edited: "已修改",
  failed: "转换失败",
};

const initialRequirementLabels: Record<string, string> = {
  generated: "已生成",
  not_generated: "未生成",
};

export default function DocumentDetailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState<RequirementOverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [selectedFileId, setSelectedFileId] = useState("");
  const [originalPreview, setOriginalPreview] = useState<OriginalPreview | null>(null);
  const [standardPreview, setStandardPreview] = useState<StandardPreview | null>(null);
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editingStandard, setEditingStandard] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [merging, setMerging] = useState(false);
  const [conflicts, setConflicts] = useState<RequirementConflict[]>([]);
  const [conflictDrafts, setConflictDrafts] = useState<Record<string, string>>({});

  const selectedFile = useMemo(
    () => overview?.files.find((file) => file.id === selectedFileId) ?? overview?.files[0] ?? null,
    [overview?.files, selectedFileId]
  );
  const showConflictTab = Boolean(overview?.has_open_conflicts || conflicts.length > 0);

  const loadConflicts = useCallback(async () => {
    try {
      const data = await apiRequest<RequirementConflict[]>(
        `/projects/${projectId}/requirements/${documentId}/conflicts`
      );
      setConflicts(data);
      setConflictDrafts(
        Object.fromEntries(data.map((conflict) => [conflict.id, conflict.resolution || conflict.fragment_a]))
      );
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "冲突列表加载失败");
    }
  }, [documentId, projectId]);

  const loadOverview = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!silent) {
        setLoading(true);
      }
      setError("");
      try {
        const data = await apiRequest<RequirementOverviewResponse>(
          `/projects/${projectId}/requirements/${documentId}/overview`
        );
        setOverview(data);
        setSelectedFileId((current) => current || data.files[0]?.id || "");
        if (data.has_open_conflicts) {
          void loadConflicts();
        } else {
          setConflicts([]);
          setConflictDrafts({});
        }
        return data;
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "需求概览加载失败");
        return null;
      } finally {
        if (!silent) {
          setLoading(false);
        }
      }
    },
    [documentId, loadConflicts, projectId]
  );

  const loadOriginalPreview = useCallback(async (file: SourceFile) => {
    try {
      const data = await apiRequest<{
        original_filename: string;
        file_format: string;
        content_type: "text" | "download";
        content?: string;
        download_path?: string;
      }>(`/requirement-files/${file.id}/original`);
      setOriginalPreview({
        title: data.original_filename,
        fileFormat: data.file_format,
        contentType: data.content_type,
        content: data.content ?? data.download_path ?? "",
      });
    } catch (requestError) {
      setOriginalPreview(null);
      toast.error(requestError instanceof Error ? requestError.message : "原始文件预览失败");
    }
  }, []);

  const loadStandardPreview = useCallback(async (file: SourceFile) => {
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${file.id}/markdown`);
      setStandardPreview({
        title: data.original_filename,
        markdownContent: data.markdown_content,
        conversionSummary: data.conversion_summary,
      });
      setMarkdownDraft(data.markdown_content);
    } catch (requestError) {
      setStandardPreview(null);
      setMarkdownDraft("");
      toast.error(requestError instanceof Error ? requestError.message : "标准文件加载失败");
    }
  }, []);

  useEffect(() => {
    const queryTab = searchParams.get("tab");
    if (queryTab && ["overview", "original", "standard", "initial", "conflicts"].includes(queryTab)) {
      setActiveTab(queryTab);
    }
    void loadOverview();
  }, [loadOverview, searchParams]);

  useEffect(() => {
    if (!selectedFile) {
      return;
    }
    if (activeTab === "original") {
      void loadOriginalPreview(selectedFile);
    }
    if (activeTab === "standard") {
      setEditingStandard(false);
      void loadStandardPreview(selectedFile);
    }
  }, [activeTab, loadOriginalPreview, loadStandardPreview, selectedFile]);

  function selectFileForTab(fileId: string, tab: string) {
    setSelectedFileId(fileId);
    setActiveTab(tab);
  }

  async function saveStandardMarkdown() {
    if (!selectedFile) {
      return;
    }
    setSavingStandard(true);
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${selectedFile.id}/markdown`, {
        method: "PUT",
        body: JSON.stringify({ markdown_content: markdownDraft, change_summary: "人工修订标准文件" }),
      });
      setStandardPreview({
        title: data.original_filename,
        markdownContent: data.markdown_content,
        conversionSummary: data.conversion_summary,
      });
      setEditingStandard(false);
      toast.success("标准文件已保存");
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "标准文件保存失败");
    } finally {
      setSavingStandard(false);
    }
  }

  async function mergeRequirement() {
    setMerging(true);
    try {
      const result = await apiRequest<MergeResponse>(`/projects/${projectId}/requirements/${documentId}/merge`, {
        method: "POST",
      });
      if (result.status === "merged") {
        toast.success("初始需求已生成");
        await loadOverview({ silent: true });
        setActiveTab("initial");
        return;
      }
      setConflicts(result.conflicts);
      setConflictDrafts(
        Object.fromEntries(
          result.conflicts.map((conflict) => [conflict.id, conflict.resolution || conflict.fragment_a])
        )
      );
      await loadOverview({ silent: true });
      setActiveTab("conflicts");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求合并失败");
    } finally {
      setMerging(false);
    }
  }

  async function saveConflictResolution(conflict: RequirementConflict) {
    const resolution = conflictDrafts[conflict.id]?.trim();
    if (!resolution) {
      toast.error("请填写冲突解决结果");
      return;
    }
    try {
      const result = await apiRequest<{ success: boolean; has_open_conflicts: boolean }>(
        `/projects/${projectId}/requirements/${documentId}/conflicts/${conflict.id}`,
        {
          method: "PUT",
          body: JSON.stringify({ resolution, resolution_type: "manual" }),
        }
      );
      toast.success("冲突解决结果已保存");
      await loadConflicts();
      await loadOverview({ silent: true });
      if (!result.has_open_conflicts) {
        setActiveTab("standard");
      }
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "冲突解决结果保存失败");
    }
  }

  if (loading) {
    return <SoonPage description="正在加载需求概览。" title="需求概览" />;
  }

  if (error || !overview) {
    return (
      <PageShell breadcrumbs={["项目", "需求"]} description="查看需求文件处理进度。" title="需求概览">
        <ShellSection>
          <div className="flex items-center justify-between gap-3">
            <div className="text-destructive text-sm">{error || "未找到需求文档。"}</div>
            <Button onClick={() => router.back()} variant="outline">
              <ArrowLeft className="size-4" />
              返回
            </Button>
          </div>
        </ShellSection>
      </PageShell>
    );
  }

  return (
    <PageShell
      breadcrumbs={["项目", "需求", overview.document.name]}
      description="查看原始文件、标准文件、合并冲突和初始需求。"
      title="需求概览"
    >
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          onClick={() => router.push(`/projects/${projectId}/requirements/upload?mode=append&documentId=${documentId}`)}
          type="button"
          variant="outline"
        >
          <FilePlus2 className="size-4" />
          追加文件
        </Button>
        <Button onClick={() => router.back()} variant="outline">
          <ArrowLeft className="size-4" />
          返回
        </Button>
      </div>

      <Tabs className="space-y-4" onValueChange={setActiveTab} value={activeTab}>
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="original">原始文件</TabsTrigger>
          <TabsTrigger value="standard">标准文件</TabsTrigger>
          <TabsTrigger value="initial">初始需求</TabsTrigger>
          {showConflictTab ? <TabsTrigger value="conflicts">冲突处理</TabsTrigger> : null}
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-3 md:grid-cols-4">
            <SummaryMetric label="原始文件" value={`${overview.stats.total_files}`} />
            <SummaryMetric label="可合并" value={`${overview.stats.mergeable_files}`} />
            <SummaryMetric label="待处理冲突" value={`${overview.stats.open_conflicts}`} />
            <SummaryMetric
              label="初始需求"
              value={initialRequirementLabels[overview.stats.initial_requirement_status] ?? "未生成"}
            />
          </div>
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-medium text-sm">原始文件列表</h2>
              <div className="flex flex-wrap gap-2 text-muted-foreground text-xs">
                <span>转换成功 {overview.stats.conversion_success}</span>
                <span>有警告 {overview.stats.conversion_warning}</span>
                <span>失败 {overview.stats.conversion_failed}</span>
              </div>
            </div>
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>文件名</TableHead>
                    <TableHead>格式</TableHead>
                    <TableHead>上传时间</TableHead>
                    <TableHead>转换状态</TableHead>
                    <TableHead>标准文件</TableHead>
                    <TableHead>合并状态</TableHead>
                    <TableHead>冲突</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {overview.files.map((file) => (
                    <TableRow key={file.id}>
                      <TableCell>
                        <Button
                          className="h-auto px-0 font-medium"
                          onClick={() => selectFileForTab(file.id, "original")}
                          type="button"
                          variant="link"
                        >
                          {displayFilename(file.original_filename)}
                        </Button>
                      </TableCell>
                      <TableCell>{file.file_format.toUpperCase()}</TableCell>
                      <TableCell>{formatDateTime(file.created_at)}</TableCell>
                      <TableCell>
                        <StatusBadge status={file.conversion_status} statusLabels={conversionLabels} />
                      </TableCell>
                      <TableCell>
                        <Button
                          className="h-auto px-0"
                          disabled={file.conversion_status === "failed"}
                          onClick={() => selectFileForTab(file.id, "standard")}
                          type="button"
                          variant="link"
                        >
                          {standardFileLabels[file.standard_file_status ?? ""] ?? "未生成"}
                        </Button>
                      </TableCell>
                      <TableCell>
                        <Badge variant={file.mapping_status === "pending_merge" ? "outline" : "secondary"}>
                          {mappingLabels[file.mapping_status] ?? file.mapping_status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {file.conflict_status === "open" ? (
                          <Button className="h-auto px-0" onClick={() => setActiveTab("conflicts")} variant="link">
                            待处理
                          </Button>
                        ) : (
                          <span className="text-muted-foreground text-sm">无</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {overview.files.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={7}>
                        暂无原始文件
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>
        </TabsContent>

        <TabsContent value="original">
          <ShellSection>
            <RequirementFileSwitcher
              files={overview.files}
              onSelect={setSelectedFileId}
              selectedFileId={selectedFile?.id ?? ""}
              statusLabel={(status) => conversionLabels[status] ?? status}
            />
          </ShellSection>
          <ShellSection>
            <h2 className="mb-3 font-medium text-sm">原始文件预览</h2>
            {originalPreview?.contentType === "text" ? (
              <pre className="max-h-[640px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">
                {originalPreview.content}
              </pre>
            ) : (
              <div className="rounded-lg border bg-muted/20 p-4 text-sm">
              <div className="font-medium">
                {displayFilename(originalPreview?.title ?? selectedFile?.original_filename ?? "未选择文件")}
              </div>
                <div className="mt-2 text-muted-foreground">
                  {originalPreview
                    ? `${originalPreview.fileFormat.toUpperCase()} 暂以文件访问方式查看：${originalPreview.content || "无访问路径"}`
                    : "请选择一个原始文件。"}
                </div>
              </div>
            )}
          </ShellSection>
        </TabsContent>

        <TabsContent value="standard">
          <ShellSection>
            <RequirementFileSwitcher
              files={overview.files}
              onSelect={setSelectedFileId}
              selectedFileId={selectedFile?.id ?? ""}
              statusLabel={(status) => conversionLabels[status] ?? status}
            />
          </ShellSection>
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium text-sm">{standardPreview?.title ?? "标准文件"}</h2>
                <p className="text-muted-foreground text-xs">{standardPreview?.conversionSummary ?? "选择文件后查看标准 Markdown。"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {editingStandard ? (
                  <>
                    <Button disabled={savingStandard} onClick={saveStandardMarkdown} type="button">
                      <Save className="size-4" />
                      {savingStandard ? "保存中" : "保存"}
                    </Button>
                    <Button
                      disabled={savingStandard}
                      onClick={() => {
                        setMarkdownDraft(standardPreview?.markdownContent ?? "");
                        setEditingStandard(false);
                      }}
                      type="button"
                      variant="outline"
                    >
                      <X className="size-4" />
                      取消
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      disabled={!standardPreview}
                      onClick={() => setEditingStandard(true)}
                      type="button"
                      variant="outline"
                    >
                      <Pencil className="size-4" />
                      修改
                    </Button>
                    <Button disabled={merging || overview.stats.mergeable_files === 0} onClick={mergeRequirement} type="button">
                      <GitMerge className="size-4" />
                      {merging ? "合并中" : "合并"}
                    </Button>
                  </>
                )}
              </div>
            </div>
            {editingStandard ? (
              <Textarea
                className="min-h-[560px] font-mono text-sm"
                onChange={(event) => setMarkdownDraft(event.target.value)}
                value={markdownDraft}
              />
            ) : (
              <MarkdownPreview
                className="requirement-document-preview"
                content={standardPreview?.markdownContent ?? ""}
                emptyText="当前文件暂无可展示的标准 Markdown。"
                indentParagraphs
              />
            )}
            <div className="mt-3 text-muted-foreground text-xs">合并会处理当前需求下全部可用标准文件。</div>
          </ShellSection>
        </TabsContent>

        <TabsContent value="initial">
          <MarkdownPreview
            className="requirement-document-preview"
            content={overview.initial_markdown_content}
            emptyText="尚未生成初始需求，请先在标准文件中发起合并。"
            indentParagraphs
          />
        </TabsContent>

        {showConflictTab ? (
          <TabsContent value="conflicts">
            <div className="space-y-4">
              {conflicts.map((conflict) => (
                <ShellSection key={conflict.id}>
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-medium text-sm">{conflict.title}</h2>
                      <p className="text-muted-foreground text-xs">来源：{conflict.source_file_names}</p>
                    </div>
                    <Badge variant="outline">待处理</Badge>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-sm">
                      {conflict.fragment_a}
                    </pre>
                    <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-3 text-sm">
                      {conflict.fragment_b}
                    </pre>
                  </div>
                  <div className="mt-4 grid gap-2">
                    <Textarea
                      className="min-h-28"
                      onChange={(event) =>
                        setConflictDrafts((current) => ({ ...current, [conflict.id]: event.target.value }))
                      }
                      value={conflictDrafts[conflict.id] ?? ""}
                    />
                    <div className="flex justify-end">
                      <Button onClick={() => saveConflictResolution(conflict)} type="button">
                        <Check className="size-4" />
                        保存解决结果
                      </Button>
                    </div>
                  </div>
                </ShellSection>
              ))}
              {conflicts.length === 0 ? (
                <ShellSection>
                  <div className="text-muted-foreground text-sm">暂无待处理冲突。</div>
                </ShellSection>
              ) : null}
            </div>
          </TabsContent>
        ) : null}
      </Tabs>
    </PageShell>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <ShellSection>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="mt-2 font-semibold text-2xl tabular-nums">{value}</div>
    </ShellSection>
  );
}

function StatusBadge({ status, statusLabels }: { status: string; statusLabels: Record<string, string> }) {
  return <Badge variant={status === "failed" ? "destructive" : "secondary"}>{statusLabels[status] ?? status}</Badge>;
}

function displayFilename(filename: string) {
  return filename.split(/[\\/]/).filter(Boolean).pop() ?? filename;
}
