"use client";

import { useState } from "react";

import { Eye, PlaySquare } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const suites = [
  { id: "suite-001", name: "登录流程自动化", status: "可执行", passRate: "96%", updated: "2026-05-19 12:30:00" },
  { id: "suite-002", name: "项目管理自动化", status: "生成中", passRate: "-", updated: "2026-05-19 08:30:00" },
  { id: "suite-003", name: "报告中心自动化", status: "失败待诊断", passRate: "72%", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(suites);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.id, item.name, item.status, item.passRate, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "UI 自动化"]}
      description="基于 pytest + Playwright + Allure 生成、查看、执行和诊断 UI 自动化。"
      projectScope="project"
      tabs={["套件列表", "代码查看", "本地执行", "Allure 报告", "失败诊断"]}
      title="UI 自动化"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="可执行 15 个" icon={PlaySquare} label="自动化套件" value="18" />
        <MetricCard helper="失败 7 条" icon={PlaySquare} label="最近通过率" value="88%" />
        <MetricCard helper="需人工启用自愈" icon={PlaySquare} label="待诊断" value="5" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="生成自动化"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索套件、用例或执行记录"
          selectedCount={selectedCount}
          title="自动化套件列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部自动化套件"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>套件编号</TableHead>
                <TableHead>套件名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>通过率</TableHead>
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
                  <TableCell className="font-medium">{item.id}</TableCell>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "可执行" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.passRate}</TableCell>
                  <TableCell>{item.updated}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", icon: Eye }]} label={`打开 ${item.name} 操作菜单`} />
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
