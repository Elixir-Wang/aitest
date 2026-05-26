"use client";

import { useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import { AlertTriangle, CheckCircle2, Clock3, Eye, ListTodo, Radar } from "lucide-react";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProjectContextStore } from "@/stores/project-context-store";

const tasks: Array<{ id: string; project: string; name: string; status: string; updated: string }> = [];

export default function Page() {
  const router = useRouter();
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const { allSelected, deleteSelected, partiallySelected, rows, selectedCount, selectedIds, toggleAll, toggleOne } =
    useLocalTableSelection(tasks);
  const [searchText, setSearchText] = useState("");

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const filteredRows = rows.filter((task) =>
    [task.project, task.name, task.status, task.updated].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

  function openExplorationTaskCreate() {
    router.push("/exploration?create=exploration");
  }

  return (
    <PageShell
      breadcrumbs={["工作台", "任务中心"]}
      description="汇总需求分析、探索、知识库、用例、UI 自动化和失败诊断任务。"
      projectScope="all"
      tabs={["全部任务", "等待人工", "失败任务", "任务详情"]}
      title="任务中心"
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard helper="真实接口接入后展示" icon={ListTodo} label="全部任务" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={Clock3} label="运行中" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={AlertTriangle} label="等待人工" value="-" />
        <MetricCard helper="真实接口接入后展示" icon={CheckCircle2} label="成功率" value="-" />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建探索任务"
          onBatchDelete={deleteSelected}
          onCreate={openExplorationTaskCreate}
          onSearch={setSearchText}
          placeholder="搜索任务种类、模块或项目"
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
                <TableHead>项目</TableHead>
                <TableHead>任务种类</TableHead>
                <TableHead>状态</TableHead>
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
                  <TableCell>{task.project}</TableCell>
                  <TableCell className="font-medium">{task.name}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        task.status === "失败" ? "destructive" : task.status === "等待人工" ? "outline" : "secondary"
                      }
                    >
                      {task.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{task.updated}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        { label: "查看", href: "/tasks", icon: Eye },
                        {
                          label: "新建探索任务",
                          href: "/exploration?create=exploration",
                          icon: Radar,
                        },
                      ]}
                      label="打开操作菜单"
                    />
                  </TableCell>
                </TableRow>
              ))}
              {filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    暂无任务。发起需求分析、站点探索或自动化执行后，任务进度会显示在这里。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
    </PageShell>
  );
}
