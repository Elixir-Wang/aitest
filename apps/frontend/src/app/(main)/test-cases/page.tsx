"use client";

import { useState } from "react";

import { ClipboardCheck, Eye } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const testCases = [
  { id: "tc-001", title: "登录成功", status: "已采纳", module: "登录与权限", updated: "2026-05-19 14:48:00" },
  { id: "tc-002", title: "项目列表筛选", status: "待审", module: "项目管理", updated: "2026-05-19 10:30:00" },
  { id: "tc-003", title: "报告导出", status: "已采纳", module: "报告中心", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(testCases);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.module, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目工作区", "测试用例"]}
      description="查看全部项目的测试用例、采纳状态和更新时间。"
      projectScope="all"
      title="测试用例"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="已采纳 2 个" icon={ClipboardCheck} label="测试用例" value="3" />
        <MetricCard helper="待审 1 个" icon={ClipboardCheck} label="采纳状态" value="2/3" />
        <MetricCard helper="覆盖 3 个模块" icon={ClipboardCheck} label="模块覆盖" value="3" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建用例"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索用例、模块或状态"
          selectedCount={selectedCount}
          title="测试用例列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部测试用例"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用例标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>所属模块</TableHead>
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
                    <Badge variant={item.status === "已采纳" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.module}</TableCell>
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
