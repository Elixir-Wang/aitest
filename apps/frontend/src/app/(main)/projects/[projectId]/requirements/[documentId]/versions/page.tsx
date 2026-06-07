"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, Check, Eye, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import {
  isFinalRequirementVersion,
  type RequirementVersionDetail,
  RequirementVersionDetailContent,
  requirementVersionActionLabel,
  requirementVersionSummary,
} from "@/components/ai-testing/requirement-version-detail-content";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

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
  const [selectedVersion, setSelectedVersion] = useState<RequirementVersionDetail | null>(null);
  const [selectedVersionLoading, setSelectedVersionLoading] = useState(false);
  const [switchingVersionId, setSwitchingVersionId] = useState("");
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

  async function openVersionDetail(version: RequirementVersionDetail) {
    setSelectedVersion(version);
    setSelectedVersionLoading(true);
    try {
      const versionDetail = await apiRequest<RequirementVersionDetail>(
        `/projects/${projectId}/requirements/${documentId}/versions/${version.id}`,
      );
      setSelectedVersion(versionDetail);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "版本详情加载失败",
        actionLabel: "查看需求版本",
        method: "GET",
        path: `/projects/${projectId}/requirements/${documentId}/versions/${version.id}`,
      });
      setSelectedVersion(null);
    } finally {
      setSelectedVersionLoading(false);
    }
  }

  async function switchVersion(version: RequirementVersionDetail) {
    setSwitchingVersionId(version.id);
    try {
      await apiRequest(`/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`, {
        method: "PUT",
      });
      toast.success(`已切换为 v${version.version_no}`);
      setSelectedVersion((current) => (current ? { ...current, is_current: true } : current));
      await loadDetail();
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "版本切换失败",
        actionLabel: "切换最终需求版本",
        method: "PUT",
        path: `/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`,
      });
    } finally {
      setSwitchingVersionId("");
    }
  }

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
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>摘要</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="w-20">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {finalRequirementVersions.map((version) => (
                <TableRow key={version.id}>
                  <TableCell>{`v${version.version_no}`}</TableCell>
                  <TableCell className="max-w-2xl whitespace-normal">{requirementVersionSummary(version)}</TableCell>
                  <TableCell>{formatDateTime(version.created_at)}</TableCell>
                  <TableCell>
                    <Button
                      aria-label="查看版本详情"
                      onClick={() => {
                        void openVersionDetail(version);
                      }}
                      size="icon-sm"
                      type="button"
                      variant="ghost"
                    >
                      <Eye className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
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
      <Dialog
        onOpenChange={(open) => {
          if (!open) {
            setSelectedVersion(null);
            setSelectedVersionLoading(false);
          }
        }}
        open={Boolean(selectedVersion)}
      >
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-4xl">
          <DialogHeader className="shrink-0 gap-2 px-6 pt-6 pb-4">
            <DialogTitle>版本详情</DialogTitle>
            <DialogDescription>
              {selectedVersion ? `v${selectedVersion.version_no} / ${requirementVersionActionLabel()}` : "加载中"}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-4 overflow-auto px-6 pb-6">
            {selectedVersionLoading ? (
              <div className="flex items-center gap-2 rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin" />
                正在加载版本最终需求
              </div>
            ) : null}
            {selectedVersion ? <RequirementVersionDetailContent version={selectedVersion} /> : null}
          </div>
          <DialogFooter className="border-t px-6 py-4">
            <Button
              disabled={[
                !selectedVersion,
                selectedVersionLoading,
                selectedVersion ? switchingVersionId === selectedVersion.id : false,
                selectedVersion ? selectedVersion.id === detail.document.current_version_id : false,
                selectedVersion?.is_current === true,
              ].some(Boolean)}
              onClick={() => {
                if (selectedVersion) {
                  void switchVersion(selectedVersion);
                }
              }}
              type="button"
            >
              {selectedVersion && switchingVersionId === selectedVersion.id ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Check className="size-4" />
              )}
              {[selectedVersion?.id === detail.document.current_version_id, selectedVersion?.is_current].some(Boolean)
                ? "当前生效版本"
                : "切换为当前版本"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
