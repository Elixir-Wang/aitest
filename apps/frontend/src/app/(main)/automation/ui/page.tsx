"use client";

import { useState } from "react";

import { Eye, PlaySquare } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const automationJobs = [
  { id: "ui-001", title: "登录自动化", status: "运行中", suite: "核心回归", updated: "2026-05-19 14:48:00" },
  { id: "ui-002", title: "项目管理自动化", status: "通过", suite: "冒烟", updated: "2026-05-19 10:30:00" },
  { id: "ui-003", title: "报告中心自动化", status: "待执行", suite: "全量回归", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(automationJobs);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.suite, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目工作区", "UI 自动化"]}
      description="查看全部项目的 UI 自动化任务、套件和执行状态。"
      projectScope="all"
      title="UI 自动化"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="1 个运行中" icon={PlaySquare} label="自动化任务" value="3" />
        <MetricCard helper="覆盖 2 个套件" icon={PlaySquare} label="执行套件" value="3" />
        <MetricCard helper="1 个待执行" icon={PlaySquare} label="待执行" value="1" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建自动化"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索任务、套件或状态"
          selectedCount={selectedCount}
          title="自动化任务列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部自动化任务"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>任务标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>套件</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((item) => (
                <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${item.id}`}
                      checked={selectedIds.includes(item.id)}
                      onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "通过" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.suite}</TableCell>
                  <TableCell>{item.updated}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", href: ".", icon: Eye }]} label="打开操作菜单" />
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
