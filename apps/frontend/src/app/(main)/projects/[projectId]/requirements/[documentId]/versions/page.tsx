"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, Eye } from "lucide-react";

import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import {
  isFinalRequirementVersion,
  type RequirementVersionDetail,
  requirementVersionSummary,
} from "@/components/ai-testing/requirement-version-detail-content";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiRequest, formatDateTime } from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

type RequirementVersionPageResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    status: string;
    updated_at: string;
    current_version_id: string | null;
    current_version: {
      id?: string;
      version_no: number;
      change_summary: string;
      created_at: string;
    } | null;
  };
  versions: RequirementVersionDetail[];
};

export default function RequirementVersionsPage() {
  const router = useRouter();
  const params = useParams<{ projectId: string; documentId: string }>();
  const { projectId, documentId } = params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<RequirementVersionPageResponse | null>(null);
  const finalRequirementVersions = useMemo(
    () => detail?.versions.filter(isFinalRequirementVersion) ?? [],
    [detail?.versions],
  );

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
      <PageShell
        breadcrumbs={moduleBreadcrumbs("requirements", { label: "版本记录" })}
        description="查看需求文档每个版本的变更信息。"
        title="版本记录"
      >
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
      breadcrumbs={moduleBreadcrumbs(
        "requirements",
        { label: detail.document.name, href: `/projects/${projectId}/requirements/${documentId}` },
        { label: "版本记录" },
      )}
      description="记录该需求每次最终需求变更的摘要与创建时间。"
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
              {detail.document.current_version ? `v${detail.document.current_version.version_no}` : "尚未生成最终需求"}
            </p>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-24 pl-5">版本</TableHead>
                <TableHead>摘要</TableHead>
                <TableHead className="w-48">创建时间</TableHead>
                <TableHead className="w-20 text-center">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {finalRequirementVersions.map((version) => {
                const versionHref = `/projects/${projectId}/requirements/${documentId}/versions/${version.id}`;

                return (
                  <TableRow key={version.id}>
                    <TableCell className="pl-5">
                      <Link className="font-medium text-primary hover:underline" href={versionHref}>
                        {`v${version.version_no}`}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <div className="truncate text-foreground" title={requirementVersionSummary(version)}>
                        {requirementVersionSummary(version)}
                      </div>
                    </TableCell>
                    <TableCell>{formatDateTime(version.created_at)}</TableCell>
                    <TableCell className="text-center">
                      <Button aria-label="预览版本" asChild size="icon-sm" variant="ghost">
                        <Link href={versionHref}>
                          <Eye className="size-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
              {finalRequirementVersions.length === 0 ? (
                <TableRow>
                  <TableCell className="py-8 text-center text-muted-foreground text-sm" colSpan={4}>
                    尚未生成最终需求版本
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
