"use client";

import { useState } from "react";

import { Eye, FileText } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const requirements = [
  {
    id: "req-001",
    title: "登录与权限",
    status: "待评审",
    version: "v3",
    owner: "张敏",
    updated: "2026-05-19 12:30:00",
  },
  { id: "req-002", title: "项目管理", status: "已确认", version: "v2", owner: "李强", updated: "2026-05-19 08:30:00" },
  { id: "req-003", title: "报告中心", status: "待澄清", version: "v1", owner: "王磊", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(requirements);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.id, item.title, item.status, item.version, item.owner, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "需求"]}
      description="上传、预览、编辑需求文档，并进行 AI 分析、模块评审和澄清写回。"
      projectScope="project"
      tabs={["文档管理", "需求评审", "分析结果", "澄清问题", "版本记录"]}
      title="需求"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="1 份等待澄清" icon={FileText} label="需求文档" value="3" />
        <MetricCard helper="已确认 9 个" icon={FileText} label="模块覆盖" value="12" />
        <MetricCard helper="最近更新 2026-05-19 12:30:00" icon={FileText} label="版本记录" value="8" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="上传需求"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索需求文档、模块或状态"
          selectedCount={selectedCount}
          title="需求文档列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部需求"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>需求编号</TableHead>
                <TableHead>需求标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>版本</TableHead>
                <TableHead>负责人</TableHead>
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
                  <TableCell>{item.title}</TableCell>
                  <TableCell>
                    <Badge variant={item.status === "已确认" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.version}</TableCell>
                  <TableCell>{item.owner}</TableCell>
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
