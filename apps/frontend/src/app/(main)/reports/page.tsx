"use client";

import { useState } from "react";

import { Activity, ClipboardList, Eye, FileClock } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const reports = [
  { id: "r-2101", project: "知了平台", name: "UI 自动化周报", status: "完成", updated: "2026-05-19 12:30:00" },
  { id: "r-2102", project: "知了平台", name: "失败诊断摘要", status: "处理中", updated: "2026-05-19 09:30:00" },
  { id: "r-2103", project: "鹰眼平台", name: "Allure 报告", status: "完成", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(reports);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((report) =>
    [report.id, report.project, report.name, report.status, report.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["测试资产", "报告中心"]}
      description="按全局或项目范围查看运行记录、Allure 报告、失败诊断和内部 Bug 记录。"
      projectScope="all"
      tabs={["运行记录", "Allure 报告", "失败诊断", "内部 Bug 记录"]}
      title="报告中心"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="近 30 天" icon={Activity} label="运行记录" value="94" />
        <MetricCard helper="可跳转查看" icon={ClipboardList} label="Allure 报告" value="31" />
        <MetricCard helper="已关闭 12 个" icon={FileClock} label="失败诊断" value="17" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建报告"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索报告、任务或失败原因"
          selectedCount={selectedCount}
          title="报告列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部报告"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>报告编号</TableHead>
                <TableHead>项目</TableHead>
                <TableHead>报告名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((report) => (
                <TableRow data-state={selectedIds.includes(report.id) ? "selected" : undefined} key={report.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${report.id}`}
                      checked={selectedIds.includes(report.id)}
                      onCheckedChange={(checked) => toggleOne(report.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{report.id}</TableCell>
                  <TableCell>{report.project}</TableCell>
                  <TableCell>{report.name}</TableCell>
                  <TableCell>
                    <Badge variant={report.status === "完成" ? "secondary" : "outline"}>{report.status}</Badge>
                  </TableCell>
                  <TableCell>{report.updated}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", href: "/reports", icon: Eye }]} label="打开操作菜单" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
    </PageShell>
  );
}
