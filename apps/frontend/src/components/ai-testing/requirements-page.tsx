"use client";

import { useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Eye, History, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Checkbox } from "@/components/ui/checkbox";
import { requirementAnalysisStatusTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type RequirementRow = {
  id: string;
  project_id: string;
  project_name?: string;
  name: string;
  document_type: string;
  file_count: number;
  status: string;
  created_at: string;
  updated_at: string;
  current_version_id: string | null;
  latest_requirement_analysis_run: {
    id: string;
    status: string;
    summary: string;
    failure_reason: string;
    created_at: string;
    updated_at: string;
  } | null;
  available_actions: string[];
};

type RequirementPageProps = {
  title: string;
  breadcrumbs: string[];
  projectScope: "all" | "project";
  description: string;
  projectId?: string;
  uploadHref: string;
};

export type RequirementDeleteResult = {
  id: string;
  name: string;
  ok: boolean;
  error?: unknown;
};

function requirementDeleteErrorMessage(error: unknown) {
  if (error instanceof Error && error.message === "Failed to fetch") {
    return "网络异常，未收到后端响应";
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "未知错误";
}

function summarizeRequirementDeleteReason(error: unknown) {
  const message = requirementDeleteErrorMessage(error);
  if (message.includes("已关联测试用例集")) {
    return "已关联测试用例集，需先删除测试用例集";
  }
  return message;
}

function summarizeRequirementDeleteResults(results: RequirementDeleteResult[]) {
  const successful = results.filter((item) => item.ok);
  const failed = results.filter((item) => !item.ok);
  const failedNames = failed.map((item) => item.name).join("、");
  const failedReasons = Array.from(new Set(failed.map((item) => summarizeRequirementDeleteReason(item.error))));
  const reasonSummary = failedReasons.join("；");

  return {
    successfulIds: successful.map((item) => item.id),
    successCount: successful.length,
    failedCount: failed.length,
    failedNames,
    failureMessage: failed.length > 0 ? `删除失败：${reasonSummary}` : "",
  };
}

const statusLabels: Record<string, string> = {
  parsing: "解析中",
  pending_merge: "待选择主需求",
  pending_review: "待评审",
  versioned: "已生成",
};

const requirementAnalysisRunStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "分析中",
  completed: "分析完成",
  needs_clarification: "等待澄清",
  blocked: "分析阻塞",
  failed: "分析失败",
};

function requirementDisplayStatus(item: RequirementRow) {
  const latestRun = item.latest_requirement_analysis_run;
  const hasFinalRequirement = Boolean(item.current_version_id);
  if (latestRun && (!hasFinalRequirement || ["queued", "running"].includes(latestRun.status))) {
    return {
      isProcessing: ["queued", "running"].includes(latestRun.status),
      label: requirementAnalysisRunStatusLabels[latestRun.status] ?? latestRun.status,
      tone: requirementAnalysisStatusTone(latestRun.status),
    } as const;
  }
  return {
    isProcessing: item.status === "parsing",
    label: statusLabels[item.status] ?? item.status,
    tone: requirementAnalysisStatusTone(item.status),
  } as const;
}

export function RequirementsPage({
  title,
  breadcrumbs,
  projectScope,
  description,
  projectId,
  uploadHref,
}: RequirementPageProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const {
    allSelected,
    clearSelection,
    partiallySelected,
    rows,
    selectedCount,
    selectedIds,
    setRows,
    toggleAll,
    toggleOne,
  } = useLocalTableSelection<RequirementRow>([]);

  const showProjectColumn = projectScope === "all";

  useEffect(() => {
    let ignore = false;

    async function loadDocuments() {
      setLoading(true);
      setError("");
      try {
        const path = projectScope === "project" && projectId ? `/projects/${projectId}/requirements` : "/requirements";
        const data = await apiRequest<RequirementRow[]>(path);
        if (!ignore) {
          setRows(data);
        }
      } catch (requestError) {
        if (!ignore) {
          reportError(requestError, {
            fallbackMessage: "需求文档加载失败",
            actionLabel: "加载需求文档",
            method: "GET",
            path: projectScope === "project" && projectId ? `/projects/${projectId}/requirements` : "/requirements",
          });
          setError(requestError instanceof Error ? requestError.message : "需求文档加载失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadDocuments();

    return () => {
      ignore = true;
    };
  }, [projectId, projectScope, setRows]);

  const filteredRows = useMemo(
    () =>
      rows.filter((item) => {
        const displayStatus = requirementDisplayStatus(item);
        return [
          item.name,
          item.project_name ?? "",
          String(item.file_count),
          item.status,
          displayStatus.label,
          item.latest_requirement_analysis_run?.summary ?? "",
          item.latest_requirement_analysis_run?.failure_reason ?? "",
          item.updated_at,
        ].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase()));
      }),
    [rows, searchText],
  );

  async function deleteDocuments(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    const targets = rows.filter((row) => ids.includes(row.id));
    const results = await Promise.all(
      targets.map(async (row): Promise<RequirementDeleteResult> => {
        try {
          await apiRequest(`/projects/${row.project_id}/requirements/${row.id}`, {
            method: "DELETE",
          });
          return { id: row.id, name: row.name, ok: true };
        } catch (error) {
          return { id: row.id, name: row.name, ok: false, error };
        }
      }),
    );
    const summary = summarizeRequirementDeleteResults(results);

    if (summary.successCount > 0) {
      const successfulIds = summary.successfulIds;
      setRows((current) => current.filter((row) => !successfulIds.includes(row.id)));
      clearSelection();
    }

    if (summary.failedCount === 0) {
      toast.success(`已删除 ${summary.successCount} 个需求文档`);
      return;
    }

    reportError(new Error(summary.failureMessage), {
      fallbackMessage: summary.successCount > 0 ? "部分需求文档删除失败" : "需求文档删除失败",
      actionLabel: `删除需求文档：${summary.failedNames}`,
      method: "DELETE",
      path: "/projects/{projectId}/requirements/{documentId}",
    });
  }

  return (
    <PageShell breadcrumbs={breadcrumbs} description={description} projectScope={projectScope} title={title}>
      <ShellSection>
        {error ? (
          <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
            {error}
          </div>
        ) : null}
        <ListToolbar
          createLabel="新建需求"
          onBatchDelete={() => deleteDocuments(selectedIds)}
          onCreate={() => router.push(uploadHref)}
          onSearch={setSearchText}
          placeholder="搜索需求名称、文件数量、状态或更新时间"
          selectedCount={selectedCount}
          title="需求列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部需求"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>需求名称</TableHead>
                {showProjectColumn ? <TableHead>所属项目</TableHead> : null}
                <TableHead>文件数量</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((item) => {
                const displayStatus = requirementDisplayStatus(item);
                return (
                  <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                    <TableCell>
                      <Checkbox
                        aria-label={`选择 ${item.name}`}
                        checked={selectedIds.includes(item.id)}
                        onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <Link
                        className="block truncate hover:underline"
                        href={`/projects/${item.project_id}/requirements/${item.id}`}
                        title={item.name}
                      >
                        {item.name}
                      </Link>
                    </TableCell>
                    {showProjectColumn ? (
                      <TableCell className="text-muted-foreground">{item.project_name || "-"}</TableCell>
                    ) : null}
                    <TableCell>{item.file_count}</TableCell>
                    <TableCell>
                      <StatusBadge tone={displayStatus.tone}>
                        {displayStatus.isProcessing ? (
                          <ProcessingState label={displayStatus.label} />
                        ) : (
                          displayStatus.label
                        )}
                      </StatusBadge>
                    </TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          {
                            label: "概览",
                            href: `/projects/${item.project_id}/requirements/${item.id}`,
                            icon: Eye,
                          },
                          {
                            label: "版本记录",
                            href: `/projects/${item.project_id}/requirements/${item.id}/versions`,
                            icon: History,
                          },
                          {
                            label: "删除",
                            icon: Trash2,
                            destructive: true,
                            onSelect: () => deleteDocuments([item.id]),
                          },
                        ]}
                        label={`打开 ${item.name} 操作菜单`}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
              {loading && filteredRows.length === 0 ? (
                <TableLoadingRow colSpan={showProjectColumn ? 7 : 6} label="需求文档加载中" />
              ) : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={showProjectColumn ? 7 : 6}>
                    暂无需求文档。上传或新建需求后，可在这里查看分析结果和版本记录。
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
