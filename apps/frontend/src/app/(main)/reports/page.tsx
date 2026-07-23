"use client";

import { useState } from "react";

import { Eye } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Checkbox } from "@/components/ui/checkbox";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const reports: Array<{ id: string; project: string; name: string; status: string; updated: string }> = [];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(reports);
  const [searchText, setSearchText] = useState("");

  const filteredRows = rows.filter((report) =>
    [report.project, report.name, report.status, report.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("reports")}
      description="按全局或项目范围查看接口、性能和 UI 测试报告。"
      projectScope="all"
      tabs={["接口", "性能", "UI"]}
      title="报告中心"
    >
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
                  <TableCell>{report.project}</TableCell>
                  <TableCell>{report.name}</TableCell>
                  <TableCell>
                    <StatusBadge tone={chineseCompletionTone(report.status)}>
                      {report.status === "处理中" ? <ProcessingState label={report.status} /> : report.status}
                    </StatusBadge>
                  </TableCell>
                  <TableCell>{report.updated}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", href: "/reports", icon: Eye }]} label="打开操作菜单" />
                  </TableCell>
                </TableRow>
              ))}
              {filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    暂无报告。测试任务完成后，报告会汇总展示在这里。
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
