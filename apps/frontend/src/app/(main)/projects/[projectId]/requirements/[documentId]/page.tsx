"use client";

import { useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ArrowLeft } from "lucide-react";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
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

  useEffect(() => {
    let ignore = false;

    async function loadDetail() {
      setLoading(true);
      setError("");
      try {
        const data = await apiRequest<DocumentDetailResponse>(`/projects/${projectId}/requirements/${documentId}`);
        if (!ignore) {
          setDetail(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "需求文档详情加载失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadDetail();

    return () => {
      ignore = true;
    };
  }, [documentId, projectId]);

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
      onPrimaryAction={() => router.back()}
      primaryAction="返回"
      title="需求文档详情"
    >
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
    </PageShell>
  );
}
