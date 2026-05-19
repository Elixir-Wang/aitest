"use client";

import { useState } from "react";

import { AlertTriangle, CheckCircle2, Clock3, ListTodo } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const tasks = [
  {
    id: "t-1001",
    project: "知了平台",
    name: "需求分析",
    status: "运行中",
    owner: "张敏",
    updated: "2026-05-19 14:48:00",
  },
  {
    id: "t-1002",
    project: "知了平台",
    name: "探索任务",
    status: "等待人工",
    owner: "李强",
    updated: "2026-05-19 14:36:00",
  },
  {
    id: "t-1003",
    project: "鹰眼平台",
    name: "用例生成",
    status: "成功",
    owner: "陈晨",
    updated: "2026-05-19 13:30:00",
  },
  {
    id: "t-1004",
    project: "鹰眼平台",
    name: "UI 自动化",
    status: "失败",
    owner: "王磊",
    updated: "2026-05-19 12:30:00",
  },
];

export default function Page() {
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(tasks);
  const [searchText, setSearchText] = useState("");
  const filteredRows = rows.filter((task) =>
    [task.id, task.project, task.name, task.status, task.owner, task.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  return (
    <PageShell
      breadcrumbs={["工作台", "任务中心"]}
      description="汇总需求分析、探索、知识库、用例、UI 自动化和失败诊断任务。"
      projectScope="all"
      tabs={["全部任务", "等待人工", "失败任务", "任务详情"]}
      title="任务中心"
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard helper="近 7 天 36 个" icon={ListTodo} label="全部任务" value="128" />
        <MetricCard helper="平均耗时 12 分钟" icon={Clock3} label="运行中" value="9" />
        <MetricCard helper="需要评审或确认" icon={AlertTriangle} label="等待人工" value="3" />
        <MetricCard helper="失败 5 个" icon={CheckCircle2} label="成功率" value="91%" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建任务"
          description="汇总需求分析、探索、知识库、用例与自动化任务。"
          onBatchDelete={deleteSelected}
          onDelete={deleteSelected}
          onSearch={setSearchText}
          placeholder="搜索任务名称、模块或项目"
          selectedCount={selectedCount}
          title="任务列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部任务"
                    checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                    onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>任务编号</TableHead>
                <TableHead>项目</TableHead>
                <TableHead>任务名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>负责人</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((task) => (
                <TableRow data-state={selectedIds.includes(task.id) ? "selected" : undefined} key={task.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${task.id}`}
                      checked={selectedIds.includes(task.id)}
                      onCheckedChange={(checked) => toggleOne(task.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="font-medium">{task.id}</TableCell>
                  <TableCell>{task.project}</TableCell>
                  <TableCell>{task.name}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        task.status === "失败" ? "destructive" : task.status === "等待人工" ? "outline" : "secondary"
                      }
                    >
                      {task.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{task.owner}</TableCell>
                  <TableCell>{task.updated}</TableCell>
                  <TableCell>
                    <RowActions actions={[{ label: "查看", href: "/tasks" }]} label="打开操作菜单" />
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
