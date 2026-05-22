"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, Eye } from "lucide-react";

import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiRequest, formatDateTime } from "@/lib/api-client";

type RequirementVersionPageResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    status: string;
    updated_at: string;
    current_version: {
      version_no: number;
      change_summary: string;
      created_at: string;
    } | null;
  };
  versions: Array<{
    id: string;
    version_no: number;
    source_action: string;
    change_summary: string;
    diff_summary: string;
    created_at: string;
  }>;
};

export default function RequirementVersionsPage() {
  const router = useRouter();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<RequirementVersionPageResponse | null>(null);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<RequirementVersionPageResponse>(
        `/projects/${projectId}/requirements/${documentId}`,
      );
      setDetail(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "版本记录加载失败");
    } finally {
      setLoading(false);
    }
  }, [documentId, projectId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  if (loading) {
    return <SoonPage description="正在加载需求版本记录。" title="版本记录" />;
  }

  if (error || !detail) {
    return (
      <PageShell breadcrumbs={["项目", "需求"]} description="查看需求文档每个版本的变更信息。" title="版本记录">
        <ShellSection>
          <div className="flex items-center justify-between gap-3">
            <div className="text-destructive text-sm">{error || "未找到需求文档版本记录。"}</div>
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
      breadcrumbs={["项目", "需求", detail.document.name, "版本记录"]}
      description="记录该需求每个版本的来源动作、变更说明、差异摘要与创建时间。"
      title="版本记录"
    >
      <div className="flex flex-wrap justify-end gap-2">
        <Button asChild variant="outline">
          <Link href={`/projects/${projectId}/requirements/${documentId}`}>
            <Eye className="size-4" />
            概览
          </Link>
        </Button>
        <Button onClick={() => router.back()} variant="outline">
          <ArrowLeft className="size-4" />
          返回
        </Button>
      </div>

      <ShellSection>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-medium text-sm">{detail.document.name}</h2>
            <p className="text-muted-foreground text-sm">
              当前版本：
              {detail.document.current_version ? `v${detail.document.current_version.version_no}` : "尚未生成工作稿"}
            </p>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>来源动作</TableHead>
                <TableHead>变更说明</TableHead>
                <TableHead>差异摘要</TableHead>
                <TableHead>创建时间</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {detail.versions.map((version) => (
                <TableRow key={version.id}>
                  <TableCell>{`v${version.version_no}`}</TableCell>
                  <TableCell>{version.source_action}</TableCell>
                  <TableCell>{version.change_summary || "-"}</TableCell>
                  <TableCell className="max-w-md whitespace-normal">{version.diff_summary || "-"}</TableCell>
                  <TableCell>{formatDateTime(version.created_at)}</TableCell>
                </TableRow>
              ))}
              {detail.versions.length === 0 ? (
                <TableRow>
                  <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={5}>
                    尚未生成工作稿版本
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
    </PageShell>
  );
}
