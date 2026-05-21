"use client";

import { useState } from "react";

import { useParams } from "next/navigation";

import { ClipboardCheck, Eye } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const testCases: Array<{ id: string; title: string; status: string; coverage: string; updated: string }> = [];

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(testCases);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.coverage, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "测试用例"]}
      description="从知识库生成测试用例，支持人工评审、采纳和覆盖矩阵追踪。"
      projectScope="project"
      tabs={["用例列表", "用例评审", "覆盖矩阵", "版本历史"]}
      title="测试用例"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="真实接口接入后展示" icon={ClipboardCheck} label="用例总数" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={ClipboardCheck} label="待评审" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={ClipboardCheck} label="覆盖率" value="-" />
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
                <TableHead>用例标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>覆盖等级</TableHead>
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
                  <TableCell>{item.coverage}</TableCell>
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
