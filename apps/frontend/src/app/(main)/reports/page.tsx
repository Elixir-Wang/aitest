"use client";

import { useEffect, useMemo, useState } from "react";

import { Eye, Gauge } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDateTime, listReportCenterItems, type ReportCenterItem } from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const REPORT_TABS = ["接口", "性能", "UI"];

export default function Page() {
  const [activeTab, setActiveTab] = useState("性能");
  const [reports, setReports] = useState<ReportCenterItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");

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
        statusLabel(report.status),
      ].some((value) => value.toLowerCase().includes(keyword)),
    );
  }, [activeTab, reports, searchText]);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("reports")}
      description="按全局或项目范围查看接口、性能和 UI 测试报告。"
      projectScope="all"
      activeTab={activeTab}
      onTabChange={setActiveTab}
      tabs={REPORT_TABS}
      title="报告中心"
    >
      <ShellSection>
        <ListToolbar
          description="报告由测试运行自动生成并按更新时间归档。"
          onSearch={setSearchText}
          placeholder="搜索项目、压测任务或报告结论"
          title="报告列表"
        />
        <div className="overflow-x-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>项目</TableHead>
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
                <TableRow key={report.id}>
                  <TableCell className="whitespace-nowrap font-medium">{report.project_name}</TableCell>
                  <TableCell>
                    <div className="min-w-56">
                      <div className="flex items-center gap-2 font-medium">
                        <Gauge className="size-4 shrink-0 text-muted-foreground" />
                        <span>{report.name}</span>
                      </div>
                      <p className="mt-1 text-muted-foreground text-xs">分析版本 V{report.analysis_version}</p>
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
                    <StatusBadge tone={statusTone(report.status)}>
                      {isProcessing(report.status) ? (
                        <ProcessingState label={statusLabel(report.status)} />
                      ) : (
                        statusLabel(report.status)
                      )}
                    </StatusBadge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDateTime(report.updated_at)}
                  </TableCell>
                  <TableCell>
                    <RowActions
                      actions={[{ label: "查看报告", href: report.href, icon: Eye }]}
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
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
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

function statusLabel(status: ReportCenterItem["status"]) {
  return { collecting: "采集证据", analyzing: "智能分析中", completed: "已生成", failed: "生成失败" }[status];
}

function statusTone(status: ReportCenterItem["status"]): StatusBadgeTone {
  if (status === "completed") return "success";
  if (status === "failed") return "destructive";
  return "processing";
}

function isProcessing(status: ReportCenterItem["status"]) {
  return status === "collecting" || status === "analyzing";
}
