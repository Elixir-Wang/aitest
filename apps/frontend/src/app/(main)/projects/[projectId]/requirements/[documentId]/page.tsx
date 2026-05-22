"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useRouter, useSearchParams } from "next/navigation";

import { ArrowLeft, Eye, FilePlus2, FileText, GitMerge, Pencil } from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, formatDateTime } from "@/lib/api-client";

type DocumentDetailResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    document_type: string;
    status: string;
    updated_at: string;
    current_version_id: string | null;
    current_version: {
      version_no: number;
      file_path: string;
      change_summary: string;
      created_at: string;
    } | null;
  };
  versions: Array<{
    id: string;
    version_no: number;
    file_path: string;
    source_action: string;
    change_summary: string;
    diff_summary: string;
    created_at: string;
  }>;
  markdown_content: string;
};

type SourceFile = {
  id: string;
  original_filename: string;
  file_format: string;
  created_at: string;
  conversion_status: string;
  mapping_status: string;
  version_id: string | null;
  version_no: number | null;
  markdown_file_path: string | null;
  conversion_summary: string;
};

type PreviewState =
  | { open: false; title: string; description: string; content: string; kind: "text" | "markdown" | "download" }
  | { open: true; title: string; description: string; content: string; kind: "text" | "markdown" | "download" };

const conversionLabels: Record<string, string> = {
  pending: "待转换",
  processing: "转换中",
  success: "转换成功",
  warning: "有警告",
  failed: "转换失败",
};

const mappingLabels: Record<string, string> = {
  pending_merge: "待归并",
  merged: "已归并",
  discarded: "已废弃",
};

export default function DocumentDetailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [filesLoading, setFilesLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [sourceFiles, setSourceFiles] = useState<SourceFile[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", change_summary: "", markdown_content: "" });
  const [preview, setPreview] = useState<PreviewState>({
    open: false,
    title: "",
    description: "",
    content: "",
    kind: "text",
  });

  const defaultTab = useMemo(() => {
    const queryTab = searchParams.get("tab");
    if (queryTab === "source-files" || queryTab === "versions" || queryTab === "draft") {
      return queryTab;
    }
    return detail?.document.current_version ? "draft" : "source-files";
  }, [detail?.document.current_version, searchParams]);

  const loadDetail = useCallback(async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) {
      setLoading(true);
    }
    setError("");
    try {
      const data = await apiRequest<DocumentDetailResponse>(`/projects/${projectId}/requirements/${documentId}`);
      setDetail(data);
      return data;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "需求文档详情加载失败");
      return null;
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, [documentId, projectId]);

  const loadSourceFiles = useCallback(async () => {
    setFilesLoading(true);
    try {
      const data = await apiRequest<SourceFile[]>(`/projects/${projectId}/requirements/${documentId}/files`);
      setSourceFiles(data);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "来源文件加载失败");
      setSourceFiles([]);
    } finally {
      setFilesLoading(false);
    }
  }, [documentId, projectId]);

  useEffect(() => {
    let ignore = false;

    async function loadInitialDetail() {
      const data = await loadDetail();
      if (ignore || !data) {
        return;
      }
      setDetail(data);
    }

    void loadInitialDetail();
    void loadSourceFiles();
    return () => {
      ignore = true;
    };
  }, [loadDetail, loadSourceFiles]);

  function openEditDialog() {
    if (!detail) {
      return;
    }
    setForm({
      name: detail.document.name,
      change_summary: "",
      markdown_content: detail.markdown_content,
    });
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!form.name.trim()) {
      toast.error("请填写需求名称");
      return;
    }
    setSaving(true);
    try {
      const updated = await apiRequest<DocumentDetailResponse>(`/projects/${projectId}/requirements/${documentId}`, {
        method: "PUT",
        body: JSON.stringify({
          name: form.name.trim(),
          markdown_content: form.markdown_content,
          change_summary: form.change_summary.trim(),
        }),
      });
      setDetail(updated);
      setDialogOpen(false);
      toast.success("需求文档已保存");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "需求文档保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function openOriginalPreview(file: SourceFile) {
    try {
      const data = await apiRequest<{
        original_filename: string;
        file_format: string;
        content_type: "text" | "download";
        content?: string;
        download_path?: string;
      }>(`/requirement-files/${file.id}/original`);
      setPreview({
        open: true,
        title: data.original_filename,
        description: data.content_type === "text" ? "原始文件内容" : "该格式暂以下载方式查看",
        content: data.content ?? data.download_path ?? "",
        kind: data.content_type,
      });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "原文件预览失败");
    }
  }

  async function openMarkdownPreview(file: SourceFile) {
    try {
      const data = await apiRequest<{
        original_filename: string;
        markdown_content: string;
        conversion_summary: string;
      }>(`/requirement-files/${file.id}/markdown`);
      setPreview({
        open: true,
        title: data.original_filename,
        description: data.conversion_summary || "转换稿 Markdown",
        content: data.markdown_content,
        kind: "markdown",
      });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "转换稿加载失败");
    }
  }

  if (loading) {
    return <SoonPage description="正在加载需求文档详情。" title="需求文档详情" />;
  }

  if (error || !detail) {
    return (
      <PageShell breadcrumbs={["项目", "需求"]} description="查看需求文档的详情与版本记录。" title="需求文档详情">
        <ShellSection>
          <div className="flex items-center justify-between gap-3">
            <div className="text-destructive text-sm">{error || "未找到需求文档。"}</div>
            <Button variant="outline" onClick={() => router.back()}>
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
      breadcrumbs={["项目", "需求", detail.document.name]}
      description="查看需求工作稿、来源文件与版本记录。"
      onPrimaryAction={openEditDialog}
      primaryAction="编辑"
      title="需求文档详情"
    >
      <div className="flex justify-end">
        <Button onClick={() => router.back()} variant="outline">
          <ArrowLeft className="size-4" />
          返回
        </Button>
      </div>

      <Tabs defaultValue={defaultTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="draft">当前工作稿</TabsTrigger>
          <TabsTrigger value="source-files">来源文件</TabsTrigger>
          <TabsTrigger value="versions">版本记录</TabsTrigger>
        </TabsList>

        <TabsContent value="draft">
          <MarkdownPreview
            className="requirement-document-preview"
            content={detail.markdown_content}
            emptyText="尚未生成工作稿，请先在来源文件中发起归并。"
            indentParagraphs
          />
        </TabsContent>

        <TabsContent value="source-files">
          <ShellSection>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-medium text-sm">来源文件</h2>
              <Button
                type="button"
                onClick={() =>
                  router.push(`/projects/${projectId}/requirements/upload?mode=append&documentId=${documentId}`)
                }
              >
                <FilePlus2 className="size-4" />
                追加更多文件
              </Button>
            </div>
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>文件名</TableHead>
                    <TableHead>格式</TableHead>
                    <TableHead>上传时间</TableHead>
                    <TableHead>转换状态</TableHead>
                    <TableHead>归并状态</TableHead>
                    <TableHead className="w-64">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sourceFiles.map((file) => (
                    <TableRow key={file.id}>
                      <TableCell className="font-medium">{file.original_filename}</TableCell>
                      <TableCell>{file.file_format.toUpperCase()}</TableCell>
                      <TableCell>{formatDateTime(file.created_at)}</TableCell>
                      <TableCell>
                        <Badge variant={file.conversion_status === "failed" ? "destructive" : "secondary"}>
                          {conversionLabels[file.conversion_status] ?? file.conversion_status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={file.mapping_status === "pending_merge" ? "outline" : "secondary"}>
                          {mappingLabels[file.mapping_status] ?? file.mapping_status}
                          {file.version_no ? ` v${file.version_no}` : ""}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" type="button" variant="outline" onClick={() => openOriginalPreview(file)}>
                            <Eye className="size-4" />
                            预览原文件
                          </Button>
                          <Button
                            disabled={file.conversion_status === "failed"}
                            size="sm"
                            type="button"
                            variant="outline"
                            onClick={() => openMarkdownPreview(file)}
                          >
                            <FileText className="size-4" />
                            查看转换稿
                          </Button>
                          <Button disabled size="sm" type="button" variant="outline">
                            <GitMerge className="size-4" />
                            发起归并
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!filesLoading && sourceFiles.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={6}>
                        暂无来源文件
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>
        </TabsContent>

        <TabsContent value="versions">
          <ShellSection>
            <h2 className="mb-3 font-medium text-sm">版本记录</h2>
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>版本</TableHead>
                    <TableHead>来源动作</TableHead>
                    <TableHead>变更说明</TableHead>
                    <TableHead>创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.versions.map((version) => (
                    <TableRow key={version.id}>
                      <TableCell>{`v${version.version_no}`}</TableCell>
                      <TableCell>{version.source_action}</TableCell>
                      <TableCell>{version.change_summary}</TableCell>
                      <TableCell>{formatDateTime(version.created_at)}</TableCell>
                    </TableRow>
                  ))}
                  {detail.versions.length === 0 ? (
                    <TableRow>
                      <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={4}>
                        尚未生成工作稿版本
                      </TableCell>
                    </TableRow>
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>
        </TabsContent>
      </Tabs>

      <Sheet open={preview.open} onOpenChange={(open) => setPreview((current) => ({ ...current, open }))}>
        <SheetContent className="w-full sm:max-w-3xl">
          <SheetHeader>
            <SheetTitle>{preview.title}</SheetTitle>
            <SheetDescription>{preview.description}</SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-auto px-4 pb-4">
            {preview.kind === "markdown" ? (
              <MarkdownPreview content={preview.content} />
            ) : (
              <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">{preview.content}</pre>
            )}
          </div>
        </SheetContent>
      </Sheet>

      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>编辑需求文档</DialogTitle>
            <DialogDescription>保存后会生成一个新的需求文档版本。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="requirement-name">需求名称</Label>
              <Input
                id="requirement-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                value={form.name}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="requirement-change-summary">变更说明</Label>
              <Input
                id="requirement-change-summary"
                onChange={(event) => setForm((current) => ({ ...current, change_summary: event.target.value }))}
                placeholder="例如：补充验收标准"
                value={form.change_summary}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="requirement-markdown">Markdown 内容</Label>
              <Textarea
                className="min-h-96 font-mono text-sm"
                id="requirement-markdown"
                onChange={(event) => setForm((current) => ({ ...current, markdown_content: event.target.value }))}
                value={form.markdown_content}
              />
            </div>
          </div>
          <DialogFooter>
            <Button disabled={saving} onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={saving} onClick={handleSave} type="button">
              <Pencil className="size-4" />
              {saving ? "保存中" : "保存"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
