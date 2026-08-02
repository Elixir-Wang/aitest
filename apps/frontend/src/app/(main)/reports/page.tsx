"use client";

import { useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { Eye, FileChartColumn, Loader2, Trash2 } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deleteReportCenterItem, formatDateTime, listReportCenterItems, type ReportCenterItem } from "@/lib/api-client";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useAuthStore } from "@/stores/auth-store";

const REPORT_TABS = ["接口", "性能", "UI"];

export default function Page() {
  const currentUser = useAuthStore((state) => state.user);
  const [activeTab, setActiveTab] = useState("性能");
  const [reports, setReports] = useState<ReportCenterItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const canDelete = currentUser?.role === "admin";

  useEffect(() => {
    if (activeTab !== "性能") {
      setLoading(false);
      setError("");
      return;
    }
    let disposed = false;
    setLoading(true);
    setError("");
    listReportCenterItems()
      .then((items) => {
        if (!disposed) setReports(items);
      })
      .catch((requestError) => {
        if (!disposed) setError(requestError instanceof Error ? requestError.message : "报告列表加载失败");
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [activeTab]);

  const filteredRows = useMemo(() => {
    if (activeTab !== "性能") return [];
    const keyword = searchText.trim().toLowerCase();
    if (!keyword) return reports;
    return reports.filter((report) =>
      [
        report.project_name,
        report.test_name,
        report.name,
        verdictLabel(report.verdict),
        generationStatusLabel(report.generation_status),
      ].some((value) => value.toLowerCase().includes(keyword)),
    );
  }, [activeTab, reports, searchText]);

  const visibleRowIds = filteredRows.map((report) => report.id);
  const visibleSelectedIds = visibleRowIds.filter((id) => selectedIds.includes(id));
  const allVisibleSelected = visibleRowIds.length > 0 && visibleSelectedIds.length === visibleRowIds.length;
  const partiallyVisibleSelected = visibleSelectedIds.length > 0 && !allVisibleSelected;

  function toggleAllVisible(checked: boolean) {
    setSelectedIds((current) =>
      checked
        ? Array.from(new Set([...current, ...visibleRowIds]))
        : current.filter((id) => !visibleRowIds.includes(id)),
    );
  }

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((current) =>
      checked ? Array.from(new Set([...current, id])) : current.filter((selectedId) => selectedId !== id),
    );
  }

  function requestDelete(ids: string[]) {
    setSelectedIds(ids);
    setDeleteConfirmOpen(true);
  }

  async function deleteSelectedReports() {
    if (selectedIds.length === 0) return;
    const idsToDelete = [...selectedIds];
    setDeleting(true);
    try {
      const results = await Promise.allSettled(idsToDelete.map((id) => deleteReportCenterItem(id)));
      const deletedIds = idsToDelete.filter((_, index) => results[index]?.status === "fulfilled");
      const firstFailure = results.find((result) => result.status === "rejected");
      setReports((current) => current.filter((report) => !deletedIds.includes(report.id)));
      setSelectedIds(idsToDelete.filter((id) => !deletedIds.includes(id)));
      if (firstFailure?.status === "rejected") {
        const message = firstFailure.reason instanceof Error ? firstFailure.reason.message : "部分报告删除失败";
        toast.error(deletedIds.length > 0 ? `已删除 ${deletedIds.length} 份报告，其余删除失败：${message}` : message);
      } else {
        toast.success(`已删除 ${deletedIds.length} 份报告`);
        setDeleteConfirmOpen(false);
      }
    } finally {
      setDeleting(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("reports")}
      description="按全局或项目范围查看接口、性能和 UI 测试报告。"
      projectScope="all"
      activeTab={activeTab}
      onTabChange={(tab) => {
        setActiveTab(tab);
        setSelectedIds([]);
      }}
      tabs={REPORT_TABS}
      title="报告中心"
    >
      <ShellSection>
        <ListToolbar
          onBatchDelete={
            canDelete
              ? () => {
                  setSelectedIds(visibleSelectedIds);
                  setDeleteConfirmOpen(true);
                }
              : undefined
          }
          onSearch={setSearchText}
          placeholder="搜索项目、压测任务或报告结论"
          title="报告列表"
          selectedCount={visibleSelectedIds.length}
        />
        <div className="overflow-x-auto rounded-lg border bg-background">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部性能报告"
                    checked={allVisibleSelected || (partiallyVisibleSelected ? "indeterminate" : false)}
                    disabled={!(canDelete && !loading && visibleRowIds.length > 0)}
                    onCheckedChange={(checked) => toggleAllVisible(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>报告名称</TableHead>
                <TableHead>结论</TableHead>
                <TableHead>数据质量</TableHead>
                <TableHead>生成状态</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && activeTab === "性能" ? <TableLoadingRow colSpan={7} label="性能报告加载中" /> : null}
              {filteredRows.map((report) => (
                <TableRow data-state={selectedIds.includes(report.id) ? "selected" : undefined} key={report.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${report.name}`}
                      checked={selectedIds.includes(report.id)}
                      disabled={!canDelete}
                      onCheckedChange={(checked) => toggleOne(report.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="min-w-56">
                      <Link
                        className="group flex w-fit items-center gap-2 font-medium hover:text-primary"
                        href={report.href}
                      >
                        <FileChartColumn className="size-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
                        <span className="group-hover:underline">{report.name}</span>
                      </Link>
                    </div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={verdictTone(report.verdict)}>{verdictLabel(report.verdict)}</StatusBadge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={qualityTone(report.quality_status)}>
                      {qualityLabel(report.quality_status)}
                    </StatusBadge>
                  </TableCell>
                  <TableCell>
                    <StatusBadge tone={generationStatusTone(report.generation_status)}>
                      {isGenerationProcessing(report.generation_status) ? (
                        <ProcessingState label={generationStatusLabel(report.generation_status)} />
                      ) : (
                        generationStatusLabel(report.generation_status)
                      )}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDateTime(report.updated_at)}
                  </TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "查看报告", href: report.href, icon: Eye },
                        {
                          label: "删除报告",
                          icon: Trash2,
                          destructive: true,
                          disabled: !canDelete,
                          onSelect: canDelete ? () => requestDelete([report.id]) : undefined,
                        },
                      ]}
                      label={`打开 ${report.name} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {!loading && error && activeTab === "性能" ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-destructive" colSpan={7}>
                    {error}
                  </TableCell>
                </TableRow>
              ) : null}
              {!loading && !error && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-32 text-center text-muted-foreground" colSpan={7}>
                    {activeTab === "性能"
                      ? "暂无性能报告。压测运行结束后，智能分析报告会自动归档到这里。"
                      : `${activeTab}报告尚未接入。`}
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>

      <AlertDialog onOpenChange={(open) => !deleting && setDeleteConfirmOpen(open)} open={deleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <div className="flex size-10 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
              <Trash2 className="size-5" />
            </div>
            <AlertDialogTitle>删除选中的报告？</AlertDialogTitle>
            <AlertDialogDescription>
              将永久删除 {selectedIds.length} 份性能分析报告。原始压测运行和采集数据不会被删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault();
                void deleteSelectedReports();
              }}
            >
              {deleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              {deleting ? "删除中" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}

function verdictLabel(verdict: ReportCenterItem["verdict"]) {
  return { pass: "通过", conditional_pass: "有条件通过", fail: "未通过", indeterminate: "无法判定" }[verdict];
}

function verdictTone(verdict: ReportCenterItem["verdict"]): StatusBadgeTone {
  if (verdict === "pass") return "success";
  if (verdict === "fail") return "destructive";
  if (verdict === "conditional_pass") return "warning";
  return "neutral";
}

function qualityLabel(status: ReportCenterItem["quality_status"]) {
  return { complete: "完整", partial: "部分缺失", invalid: "不可用" }[status];
}

function qualityTone(status: ReportCenterItem["quality_status"]): StatusBadgeTone {
  if (status === "complete") return "success";
  if (status === "partial") return "warning";
  return "destructive";
}

function generationStatusLabel(status: ReportCenterItem["generation_status"]) {
  return { generating: "生成中", generated: "生成成功", degraded: "基础报告", failed: "生成失败" }[status];
}

function generationStatusTone(status: ReportCenterItem["generation_status"]): StatusBadgeTone {
  if (status === "generated") return "success";
  if (status === "degraded") return "warning";
  if (status === "failed") return "destructive";
  return "processing";
}

function isGenerationProcessing(status: ReportCenterItem["generation_status"]) {
  return status === "generating";
}
