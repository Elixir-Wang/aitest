"use client";

import { useState } from "react";

import { ClipboardCheck, Eye } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const testCases = [
  { id: "tc-001", title: "登录流程", status: "待评审", coverage: "高", owner: "张敏", updated: "2026-05-19 12:30:00" },
  { id: "tc-002", title: "项目创建", status: "已采纳", coverage: "中", owner: "李强", updated: "2026-05-19 08:30:00" },
  { id: "tc-003", title: "报告查看", status: "待采纳", coverage: "低", owner: "王磊", updated: "2026-05-18 10:15:00" },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(testCases);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.id, item.title, item.status, item.coverage, item.owner, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "测试用例"]}
      description="从知识库生成测试用例，支持人工评审、采纳和覆盖矩阵追踪。"
      projectScope="project"
      tabs={["用例列表", "用例评审", "覆盖矩阵", "版本历史"]}
      title="测试用例"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="采纳 351 条" icon={ClipboardCheck} label="用例总数" value="426" />
        <MetricCard helper="高优先级 6 条" icon={ClipboardCheck} label="待评审" value="28" />
        <MetricCard helper="较上次 +9%" icon={ClipboardCheck} label="覆盖率" value="76%" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="生成用例"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索用例名称、模块或优先级"
          selectedCount={selectedCount}
          title="测试用例列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部用例"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用例编号</TableHead>
                <TableHead>用例标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>覆盖等级</TableHead>
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
                    <Badge variant={item.status === "已采纳" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.coverage}</TableCell>
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
