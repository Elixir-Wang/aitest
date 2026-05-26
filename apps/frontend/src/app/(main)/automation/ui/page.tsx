"use client";

import { useState } from "react";

import { Eye, PlaySquare } from "lucide-react";

import {
  ListToolbar,
  MetricCard,
  ModuleTabs,
  PageShell,
  RowActions,
  ShellSection,
  SoonPage,
} from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const automationJobs: Array<{ id: string; title: string; status: string; suite: string; updated: string }> = [];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(automationJobs);
  const [activeTab, setActiveTab] = useState("自动化用例");
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
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="自动化任务" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="执行套件" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="待执行" value="-" />
      </div>
      <ModuleTabs activeTab={activeTab} onTabChange={setActiveTab} tabs={["自动化用例", "用例测试集"]} />
      {activeTab === "自动化用例" ? (
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
      ) : (
        <SoonPage description="用例测试集将用于组合多条 UI 自动化用例并批量执行。" title="用例测试集暂未开放" />
      )}
    </PageShell>
  );
}
