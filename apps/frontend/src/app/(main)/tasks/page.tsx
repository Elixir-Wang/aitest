import Link from "next/link";

import { AlertTriangle, ArrowRight, CheckCircle2, Clock3, ListTodo } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const tasks = [
  { id: "t-1001", project: "知了平台", name: "需求分析", status: "运行中", owner: "张敏", updated: "12 分钟前" },
  { id: "t-1002", project: "知了平台", name: "探索任务", status: "等待人工", owner: "李强", updated: "24 分钟前" },
  { id: "t-1003", project: "鹰眼平台", name: "用例生成", status: "成功", owner: "陈晨", updated: "1 小时前" },
  { id: "t-1004", project: "鹰眼平台", name: "UI 自动化", status: "失败", owner: "王磊", updated: "2 小时前" },
];

export default function Page() {
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
      <PageToolbar placeholder="搜索任务名称、模块或项目" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">任务列表</h2>
              <p className="text-muted-foreground text-xs">汇总需求分析、探索、知识库、用例与自动化任务。</p>
            </div>
            <Button variant="outline" size="sm">
              任务详情
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务编号</TableHead>
                  <TableHead>项目</TableHead>
                  <TableHead>任务名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tasks.map((task) => (
                  <TableRow key={task.id}>
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
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/tasks">
                          查看
                          <ArrowRight className="size-4" />
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>等待人工</StatusBadge>
              <span className="text-muted-foreground text-xs">当前队列 3 个</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">探索任务 / 登录流程</p>
              <p className="text-muted-foreground">任务中心只承接运行、等待人工和失败诊断，不直接承载编辑流程。</p>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看失败任务</Button>
              <Button variant="outline">处理等待项</Button>
              <Button>刷新任务</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
