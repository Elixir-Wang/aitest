"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, Pencil } from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

export default function DocumentDetailPage() {
  const router = useRouter();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: "", change_summary: "", markdown_content: "" });

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
    return () => {
      ignore = true;
    };
  }, [loadDetail]);

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
      description="查看需求文档的详情与版本记录。"
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
      <MarkdownPreview
        className="requirement-document-preview max-h-[680px] overflow-auto"
        content={detail.markdown_content}
        indentParagraphs
      />

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
            </TableBody>
          </Table>
        </div>
      </ShellSection>

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
