"use client";

import { useState } from "react";

import { useParams } from "next/navigation";

import { DatabaseZap, Eye } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const knowledge: Array<{ id: string; title: string; status: string; source: string; updated: string }> = [];

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(knowledge);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.source, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "知识库"]}
      description="基于需求和探索来源生成 llm-wiki 风格知识库，并追踪来源和版本。"
      projectScope="project"
      tabs={["知识库首页", "来源材料", "模块文档", "更新预览", "历史版本"]}
      title="知识库"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="模块文档" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="来源引用" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="待更新" value="-" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="生成知识库"
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索模块、来源或版本"
          selectedCount={selectedCount}
          title="知识库列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部知识库"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>模块标题</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>来源</TableHead>
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
                    <Badge variant={item.status === "已发布" ? "secondary" : "outline"}>{item.status}</Badge>
                  </TableCell>
                  <TableCell>{item.source}</TableCell>
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
