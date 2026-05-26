"use client";

import { useState } from "react";

import { Building2, DatabaseZap, Eye, FolderKanban } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const knowledge: Array<{ id: string; title: string; status: string; source: string; updated: string }> = [];
const knowledgeScopes = [
  { value: "project", label: "项目知识库", icon: FolderKanban },
  { value: "company", label: "公司知识库", icon: Building2 },
] as const;

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(knowledge);
  const [activeScope, setActiveScope] = useState<(typeof knowledgeScopes)[number]["value"]>("project");
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((item) =>
    [item.title, item.status, item.source, item.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );
  const isCompanyKnowledge = activeScope === "company";

  return (
    <PageShell
      breadcrumbs={["项目工作区", "知识库"]}
      description="查看项目知识库与公司知识库的知识块、来源材料和版本记录。"
      projectScope="all"
      tabs={["知识库首页", "来源材料", "模块文档", "更新预览", "历史版本"]}
      title="知识库"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="模块文档" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="来源引用" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={DatabaseZap} label="待更新" value="-" />
      </div>
      <Tabs onValueChange={(value) => setActiveScope(value as typeof activeScope)} value={activeScope}>
        <TabsList className="h-auto flex-wrap justify-start">
          {knowledgeScopes.map(({ icon: Icon, label, value }) => (
            <TabsTrigger className="h-8 gap-1.5 px-3" key={value} value={value}>
              <Icon className="size-4" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <ShellSection>
        <ListToolbar
          createLabel={isCompanyKnowledge ? "上传公司知识" : "生成知识库"}
          onBatchDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder={isCompanyKnowledge ? "搜索公司知识、类型或版本" : "搜索模块、来源或版本"}
          selectedCount={selectedCount}
          title={isCompanyKnowledge ? "公司知识库列表" : "项目知识库列表"}
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
                <TableHead>{isCompanyKnowledge ? "知识类型" : "来源"}</TableHead>
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
