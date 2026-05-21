"use client";

import { useState } from "react";

import { Eye, FileSearch } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const explorations: Array<{ id: string; title: string; status: string; site: string; updated: string }> = [];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(explorations);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.site, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目工作区", "探索"]}
      description="查看全部项目的探索任务、页面事实和冲突项。"
      projectScope="all"
      tabs={["站点配置", "探索任务", "探索文档", "候选需求文档", "冲突项"]}
      title="探索"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="真实接口接入后展示" icon={FileSearch} label="探索任务" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={FileSearch} label="页面事实" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={FileSearch} label="冲突项" value="-" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="开始探索"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索探索任务、页面或冲突项"
          selectedCount={selectedCount}
          title="探索任务列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部探索任务"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>探索标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>站点</TableHead>
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
                    <Badge variant={item.status === "完成" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.site}</TableCell>
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
