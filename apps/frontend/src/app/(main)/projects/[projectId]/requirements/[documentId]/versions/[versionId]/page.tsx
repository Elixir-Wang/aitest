"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, Check, Info, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection, SoonPage } from "@/components/ai-testing/page-shell";
import {
  type RequirementVersionDetail,
  RequirementVersionDetailContent,
  requirementVersionActionLabel,
  requirementVersionSummary,
} from "@/components/ai-testing/requirement-version-detail-content";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type RequirementVersionPreviewResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
    current_version_id: string | null;
  };
};

export default function RequirementVersionPreviewPage() {
  const router = useRouter();
  const params = useParams<{ projectId: string; documentId: string; versionId: string }>();
  const { projectId, documentId, versionId } = params;
  const [loading, setLoading] = useState(true);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");
  const [documentName, setDocumentName] = useState("");
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
  const [version, setVersion] = useState<RequirementVersionDetail | null>(null);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const versionHistoryTabPath = `/projects/${projectId}/requirements/${documentId}?tab=versions`;

  const loadVersion = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [detail, versionDetail] = await Promise.all([
        apiRequest<RequirementVersionPreviewResponse>(`/projects/${projectId}/requirements/${documentId}`),
        apiRequest<RequirementVersionDetail>(`/projects/${projectId}/requirements/${documentId}/versions/${versionId}`),
      ]);
      setDocumentName(detail.document.name);
      setCurrentVersionId(detail.document.current_version_id);
      setVersion(versionDetail);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "版本预览加载失败");
    } finally {
      setLoading(false);
    }
  }, [documentId, projectId, versionId]);

  useEffect(() => {
    void loadVersion();
  }, [loadVersion]);

  async function switchVersion() {
    if (!version) {
      return;
    }
    setSwitching(true);
    try {
      await apiRequest(`/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`, {
        method: "PUT",
      });
      toast.success(`已切换为 v${version.version_no}`);
      setCurrentVersionId(version.id);
      setVersion({ ...version, is_current: true });
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "版本切换失败",
        actionLabel: "切换最终需求版本",
        method: "PUT",
        path: `/projects/${projectId}/requirements/${documentId}/versions/${version.id}/current`,
      });
    } finally {
      setSwitching(false);
    }
  }

  if (loading) {
    return <SoonPage description="正在加载版本预览。" title="版本预览" />;
  }

  if (error || !version) {
    return (
      <PageShell breadcrumbs={["项目", "需求"]} description="查看指定需求版本的最终需求内容。" title="版本预览">
        <ShellSection>
          <div className="flex items-center justify-between gap-3">
            <div className="text-destructive text-sm">{error || "未找到版本预览。"}</div>
            <Button onClick={() => router.push(versionHistoryTabPath)} variant="outline">
              <ArrowLeft className="size-4" />
              返回
            </Button>
          </div>
        </ShellSection>
      </PageShell>
    );
  }

  const isCurrent = version.id === currentVersionId || version.is_current === true;
  const summaryRows: Array<[string, string]> = [
    ["版本", `v${version.version_no}`],
    ["状态", isCurrent ? "当前生效版本" : "历史版本"],
    ["来源动作", requirementVersionActionLabel()],
    ["摘要", requirementVersionSummary(version)],
    ["创建时间", formatDateTime(version.created_at)],
  ];

  return (
    <>
      <PageShell
        actions={
          <>
            <Button onClick={() => router.push(versionHistoryTabPath)} variant="outline">
              <ArrowLeft className="size-4" />
              返回
            </Button>
            <Button onClick={() => setSummaryOpen(true)} type="button" variant="outline">
              <Info className="size-4" />
              摘要信息
            </Button>
          </>
        }
        breadcrumbs={["项目", "需求", documentName || "需求文档", `v${version.version_no}`]}
        description="查看该版本的最终需求内容。"
        title={`v${version.version_no} 版本预览`}
      >
        <ShellSection>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">{documentName || "需求文档"}</h2>
              <p className="mt-1 text-muted-foreground text-xs">
                {isCurrent ? "当前生效版本" : "历史版本，可预览后切换为当前版本。"}
              </p>
            </div>
            <Button disabled={isCurrent || switching} onClick={() => void switchVersion()} type="button">
              {switching ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
              {isCurrent ? "当前生效版本" : "切换为当前版本"}
            </Button>
          </div>
          <RequirementVersionDetailContent version={version} />
        </ShellSection>
      </PageShell>
      <Dialog onOpenChange={setSummaryOpen} open={summaryOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>摘要信息</DialogTitle>
            <DialogDescription>查看该最终需求版本的来源、状态和变更摘要。</DialogDescription>
          </DialogHeader>
          <div className="grid min-w-0 gap-3 text-sm">
            {summaryRows.map(([label, value]) => (
              <div className="grid min-w-0 gap-1 md:grid-cols-[96px_minmax(0,1fr)] md:gap-4" key={label}>
                <span className="text-muted-foreground">{label}</span>
                <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{value}</span>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
