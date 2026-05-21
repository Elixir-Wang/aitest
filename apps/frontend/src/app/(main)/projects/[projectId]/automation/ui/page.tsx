"use client";

import { useState } from "react";

import { useParams } from "next/navigation";

import { Eye, PlaySquare } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const suites: Array<{ id: string; name: string; status: string; passRate: string; updated: string }> = [];

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(suites);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.name, item.status, item.passRate, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "UI 自动化"]}
      description="基于 pytest + Playwright + Allure 生成、查看、执行和诊断 UI 自动化。"
      projectScope="project"
      tabs={["套件列表", "代码查看", "本地执行", "Allure 报告", "失败诊断"]}
      title="UI 自动化"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="自动化套件" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="最近通过率" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="待诊断" value="-" />
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
