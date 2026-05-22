"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import {
  ArrowLeft,
  Check,
  ExternalLink,
  FileText,
  GitMerge,
  Loader2,
  Pencil,
  Save,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { ListToolbar, PageShell, RowActions, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import {
  RequirementFileSwitcher,
  type RequirementSwitcherFile,
} from "@/components/ai-testing/requirement-file-switcher";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import FileUpload1 from "@/components/ui/file-upload-1";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiBlobRequest, apiRequest, formatDateTime } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const STANDARD_FILE_SECTION_ID = "standard-file-section";

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
  standard_file_status?: "generating" | "ready" | "edited" | "failed";
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
  contentType: "text" | "file";
  content: string;
  objectUrl?: string;
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
  generating: "生成中",
  ready: "可合并",
  edited: "已修改",
  failed: "生成失败",
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
  const [standardLoading, setStandardLoading] = useState(false);
  const [standardError, setStandardError] = useState("");
  const [markdownDraft, setMarkdownDraft] = useState("");
  const [editingStandard, setEditingStandard] = useState(false);
  const [savingStandard, setSavingStandard] = useState(false);
  const [merging, setMerging] = useState(false);
  const [conflicts, setConflicts] = useState<RequirementConflict[]>([]);
  const [conflictDrafts, setConflictDrafts] = useState<Record<string, string>>({});
  const token = useAuthStore((state) => state.token);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadStates, setUploadStates] = useState<
    Record<string, { progress: number; status: "idle" | "uploading" | "completed" | "error" }>
  >({});
  const [fileSearchText, setFileSearchText] = useState("");
  const {
    allSelected: allFilesSelected,
    clearSelection: clearFileSelection,
    partiallySelected: partiallyFilesSelected,
    rows: fileRows,
    selectedCount: fileSelectedCount,
    selectedIds: fileSelectedIds,
    setRows: setFileRows,
    toggleAll: toggleAllFiles,
    toggleOne: toggleOneFile,
  } = useLocalTableSelection<SourceFile>([]);

  const selectedFile = useMemo(
    () => overview?.files.find((file) => file.id === selectedFileId) ?? overview?.files[0] ?? null,
    [overview?.files, selectedFileId],
  );
  const filteredFiles = useMemo(
    () =>
      fileRows.filter((file) =>
        [file.original_filename, file.file_format, file.conversion_status, file.mapping_status].some((value) =>
          value?.toLowerCase().includes(fileSearchText.trim().toLowerCase()),
        ),
      ),
    [fileRows, fileSearchText],
  );
  const canEditStandard = Boolean(standardPreview) && !standardLoading && standardError.length === 0;
  const showConflictTab = Boolean(overview?.has_open_conflicts || conflicts.length > 0);

  const loadConflicts = useCallback(async () => {
    try {
      const data = await apiRequest<RequirementConflict[]>(
        `/projects/${projectId}/requirements/${documentId}/conflicts`,
      );
      setConflicts(data);
      setConflictDrafts(
        Object.fromEntries(data.map((conflict) => [conflict.id, conflict.resolution || conflict.fragment_a])),
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
          `/projects/${projectId}/requirements/${documentId}/overview`,
        );
        setOverview(data);
        setFileRows(data.files);
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
    [documentId, loadConflicts, projectId, setFileRows],
  );

  const loadReadableOriginalPreview = useCallback(async (file: SourceFile) => {
    setOriginalPreview(null);
    try {
      const data = await apiRequest<{
        original_filename: string;
        file_format: string;
        content_type: "text" | "download";
        content?: string;
        download_path?: string;
      }>(`/requirement-files/${file.id}/original`);
      if (data.content_type === "text") {
        setOriginalPreview({
          title: data.original_filename,
          fileFormat: data.file_format,
          contentType: "text",
          content: data.content ?? "",
        });
        return;
      }
      const blob = await apiBlobRequest(`/requirement-files/${file.id}/original/content`);
      setOriginalPreview({
        title: data.original_filename,
        fileFormat: data.file_format,
        contentType: "file",
        content: data.download_path ?? "",
        objectUrl: URL.createObjectURL(blob),
      });
    } catch (requestError) {
      setOriginalPreview(null);
      toast.error(requestError instanceof Error ? requestError.message : "原始文件预览失败");
    }
  }, []);

  const loadStandardPreview = useCallback(async (file: SourceFile) => {
    setStandardLoading(true);
    setStandardError("");
    setStandardPreview(null);
    setMarkdownDraft("");
    if (file.standard_file_status === "generating") {
      setStandardLoading(false);
      return;
    }
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${file.id}/markdown`);
      setStandardPreview({
        title: standardMarkdownFilename(data.original_filename),
        markdownContent: data.markdown_content,
        conversionSummary: data.conversion_summary,
      });
      setMarkdownDraft(data.markdown_content);
    } catch (requestError) {
      setStandardPreview(null);
      setMarkdownDraft("");
      setStandardError(requestError instanceof Error ? requestError.message : "标准文件生成失败");
      toast.error(requestError instanceof Error ? requestError.message : "标准文件加载失败");
    } finally {
      setStandardLoading(false);
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
      void loadReadableOriginalPreview(selectedFile);
    }
    if (activeTab === "standard") {
      setEditingStandard(false);
      void loadStandardPreview(selectedFile);
    }
  }, [activeTab, loadReadableOriginalPreview, loadStandardPreview, selectedFile]);

  useEffect(() => {
    return () => {
      if (originalPreview?.objectUrl) {
        URL.revokeObjectURL(originalPreview.objectUrl);
      }
    };
  }, [originalPreview?.objectUrl]);

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
          result.conflicts.map((conflict) => [conflict.id, conflict.resolution || conflict.fragment_a]),
        ),
      );
      await loadOverview({ silent: true });
      setActiveTab("conflicts");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求合并失败");
    } finally {
      setMerging(false);
    }
  }

  async function deleteSourceFiles(ids: string[]) {
    if (ids.length === 0) return;
    try {
      await Promise.all(ids.map((id) => apiRequest(`/requirement-files/${id}`, { method: "DELETE" })));
      setFileRows((current) => current.filter((row) => !ids.includes(row.id)));
      clearFileSelection();
      toast.success(`已删除 ${ids.length} 个原始文件`);
      await loadOverview({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "原始文件删除失败");
    }
  }

  function openUploadDialog() {
    setUploadFiles([]);
    setUploadStates({});
    setUploadDialogOpen(true);
  }

  async function submitUploadFiles() {
    if (uploadFiles.length === 0) {
      toast.error("请选择至少一个文件");
      return;
    }
    const unsupported = uploadFiles.find((f) => !/\.(pdf|doc|docx|txt|md|markdown)$/i.test(f.name));
    if (unsupported) {
      toast.error(`仅支持 PDF、Word、TXT、MD 文件：${unsupported.name}`);
      return;
    }

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    setUploadSubmitting(true);
    setUploadStates(
      Object.fromEntries(
        uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 1, status: "uploading" as const }]),
      ),
    );

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${apiBase}/projects/${projectId}/requirements`);
      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        const progress = Math.min(99, Math.round((event.loaded / event.total) * 100));
        setUploadStates(
          Object.fromEntries(
            uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress, status: "uploading" as const }]),
          ),
        );
      };
      xhr.onload = () => {
        const payload = (() => {
          try {
            return JSON.parse(xhr.responseText);
          } catch {
            return null;
          }
        })();
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
          return;
        }
        reject(new Error(payload?.detail?.message ?? payload?.detail ?? "文件上传失败"));
      };
      xhr.onerror = () => reject(new Error("网络异常，文件上传失败"));
      const formData = new FormData();
      formData.append("mode", "append");
      formData.append("existing_document_id", documentId);
      for (const f of uploadFiles) {
        formData.append("files", f);
      }
      xhr.send(formData);
    })
      .then(async () => {
        setUploadStates(
          Object.fromEntries(
            uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 100, status: "completed" as const }]),
          ),
        );
        toast.success("文件已上传，正在刷新列表");
        setUploadDialogOpen(false);
        await loadOverview({ silent: true });
      })
      .catch((err: unknown) => {
        toast.error(err instanceof Error ? err.message : "文件上传失败");
        setUploadStates(
          Object.fromEntries(
            uploadFiles.map((f) => [`${f.name}-${f.size}`, { progress: 0, status: "error" as const }]),
          ),
        );
      })
      .finally(() => {
        setUploadSubmitting(false);
      });
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
        },
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
          <ShellSection className="mt-6">
            <ListToolbar
              description={`转换成功 ${overview.stats.conversion_success} · 有警告 ${overview.stats.conversion_warning} · 失败 ${overview.stats.conversion_failed}`}
              onBatchDelete={() => deleteSourceFiles(fileSelectedIds)}
              onCreate={openUploadDialog}
              onSearch={setFileSearchText}
              createLabel="上传文件"
              placeholder="搜索文件名、格式或状态"
              selectedCount={fileSelectedCount}
              title="原始文件列表"
            />
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        aria-label="选择全部文件"
                        checked={allFilesSelected || (partiallyFilesSelected ? "indeterminate" : false)}
                        onCheckedChange={(checked) => toggleAllFiles(Boolean(checked))}
                      />
                    </TableHead>
                    <TableHead>文件名</TableHead>
                    <TableHead>格式</TableHead>
                    <TableHead>上传时间</TableHead>
                    <TableHead>转换状态</TableHead>
                    <TableHead>标准文件</TableHead>
                    <TableHead>合并状态</TableHead>
                    <TableHead>冲突</TableHead>
                    <TableHead className="w-16">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredFiles.map((file) => (
                    <TableRow data-state={fileSelectedIds.includes(file.id) ? "selected" : undefined} key={file.id}>
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${displayFilename(file.original_filename)}`}
                          checked={fileSelectedIds.includes(file.id)}
                          onCheckedChange={(checked) => toggleOneFile(file.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        <button
                          className="block truncate text-left hover:underline"
                          onClick={() => selectFileForTab(file.id, "original")}
                          type="button"
                        >
                          {displayFilename(file.original_filename)}
                        </button>
                      </TableCell>
                      <TableCell>{file.file_format.toUpperCase()}</TableCell>
                      <TableCell>{formatDateTime(file.created_at)}</TableCell>
                      <TableCell>
                        <StatusBadge status={file.conversion_status} statusLabels={conversionLabels} />
                      </TableCell>
                      <TableCell>
                        <Button
                          className="h-auto px-0"
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
                      <TableCell>
                        <RowActions
                          actions={[
                            {
                              label: "查看原文",
                              icon: FileText,
                              onSelect: () => selectFileForTab(file.id, "original"),
                            },
                            {
                              label: "查看标准文件",
                              icon: FileText,
                              onSelect: () => selectFileForTab(file.id, "standard"),
                            },
                            {
                              label: "删除",
                              icon: Trash2,
                              destructive: true,
                              onSelect: () => deleteSourceFiles([file.id]),
                            },
                          ]}
                          label={`打开 ${displayFilename(file.original_filename)} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {filteredFiles.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={9}>
                        暂无原始文件
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>

          <Dialog onOpenChange={setUploadDialogOpen} open={uploadDialogOpen}>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>上传原始文件</DialogTitle>
                <DialogDescription>
                  选择文件后直接追加到当前需求，支持 PDF、Word（doc/docx）、TXT、MD 格式。
                </DialogDescription>
              </DialogHeader>
              <FileUpload1
                accept={{
                  "application/pdf": [".pdf"],
                  "application/msword": [".doc"],
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
                  "text/markdown": [".md", ".markdown"],
                  "text/plain": [".txt"],
                }}
                files={uploadFiles}
                hint="仅支持 PDF、Word（doc/docx）、TXT、MD 文件"
                maxFiles={10}
                uploadStates={uploadStates}
                onFilesChange={setUploadFiles}
              />
              <DialogFooter>
                <Button
                  disabled={uploadSubmitting}
                  onClick={() => setUploadDialogOpen(false)}
                  type="button"
                  variant="outline"
                >
                  取消
                </Button>
                <Button
                  disabled={uploadSubmitting || uploadFiles.length === 0}
                  onClick={submitUploadFiles}
                  type="button"
                >
                  {uploadSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
                  {uploadSubmitting ? "上传中" : "上传"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        <TabsContent value="original">
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium text-sm">原始文件预览</h2>
              </div>
              <RequirementFileSwitcher
                files={overview.files}
                onSelect={setSelectedFileId}
                selectedFileId={selectedFile?.id ?? ""}
              />
            </div>
            {originalPreview?.contentType === "text" ? (
              <pre className="max-h-[640px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">
                {originalPreview.content}
              </pre>
            ) : originalPreview?.objectUrl ? (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 p-3 text-sm">
                  <div>
                    <div className="font-medium">{displayFilename(originalPreview.title)}</div>
                    <div className="mt-1 text-muted-foreground">
                      {originalPreview.fileFormat.toUpperCase()} 原始文件
                    </div>
                  </div>
                  <Button asChild type="button" variant="outline">
                    <a href={originalPreview.objectUrl} rel="noreferrer" target="_blank">
                      <ExternalLink className="size-4" />
                      打开原始文件
                    </a>
                  </Button>
                </div>
                {originalPreview.fileFormat.toLowerCase() === "pdf" ? (
                  <iframe
                    className="h-[720px] w-full rounded-lg border bg-background"
                    src={originalPreview.objectUrl}
                    title={displayFilename(originalPreview.title)}
                  />
                ) : null}
              </div>
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
          <ShellSection id={STANDARD_FILE_SECTION_ID}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-medium text-sm">
                  {displayFilename(
                    standardPreview?.title ??
                      (selectedFile ? standardMarkdownFilename(selectedFile.original_filename) : "标准文件.md"),
                  )}
                </h2>
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <RequirementFileSwitcher
                  files={overview.files}
                  getFileLabel={standardMarkdownFilename}
                  onSelect={setSelectedFileId}
                  selectedFileId={selectedFile?.id ?? ""}
                />
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
                ) : null}
              </div>
            </div>
            {standardLoading ? (
              <StandardFileState
                description="系统正在生成该原始文件对应的 Markdown 标准文件，请稍后刷新。"
                title="标准文件生成中"
              />
            ) : standardError ? (
              <StandardFileState description={standardError} tone="failed" title="标准文件生成失败" />
            ) : editingStandard ? (
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
            {!editingStandard ? (
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2 border-t pt-4">
                <Button
                  onClick={() => document.getElementById(STANDARD_FILE_SECTION_ID)?.scrollIntoView()}
                  type="button"
                  variant="outline"
                >
                  <ArrowLeft className="size-4 rotate-90" />
                  返回顶部
                </Button>
                <Button
                  disabled={!canEditStandard}
                  onClick={() => setEditingStandard(true)}
                  type="button"
                  variant="outline"
                >
                  <Pencil className="size-4" />
                  修改
                </Button>
                <Button
                  disabled={merging || overview.stats.mergeable_files === 0}
                  onClick={mergeRequirement}
                  type="button"
                >
                  <GitMerge className="size-4" />
                  {merging ? "合并中" : "合并全部文件"}
                </Button>
              </div>
            ) : null}
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

function StandardFileState({
  description,
  title,
  tone = "generating",
}: {
  description: string;
  title: string;
  tone?: "generating" | "failed";
}) {
  return (
    <div className="rounded-lg border bg-muted/20 p-6 text-sm">
      <div className={tone === "failed" ? "font-medium text-destructive" : "font-medium"}>{title}</div>
      <div className="mt-2 text-muted-foreground">{description}</div>
    </div>
  );
}

function displayFilename(filename: string) {
  return filename.split(/[\\/]/).filter(Boolean).pop() ?? filename;
}

function standardMarkdownFilename(filename: string) {
  const displayName = displayFilename(filename);
  return `${displayName.replace(/\.[^.]+$/, "")}.md`;
}
