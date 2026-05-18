import Link from "next/link";

import { Activity, ArrowRight, ClipboardList, FileClock } from "lucide-react";
import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const reports = [
  { id: "r-2101", project: "知了平台", name: "UI 自动化周报", status: "完成", updated: "2 小时前" },
  { id: "r-2102", project: "知了平台", name: "失败诊断摘要", status: "处理中", updated: "5 小时前" },
  { id: "r-2103", project: "鹰眼平台", name: "Allure 报告", status: "完成", updated: "1 天前" },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["测试资产", "报告中心"]}
      description="按全局或项目范围查看运行记录、Allure 报告、失败诊断和内部 Bug 记录。"
      projectScope="all"
      tabs={["运行记录", "Allure 报告", "失败诊断", "内部 Bug 记录"]}
      title="报告中心"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="近 30 天" icon={Activity} label="运行记录" value="94" />
        <MetricCard helper="可跳转查看" icon={ClipboardList} label="Allure 报告" value="31" />
        <MetricCard helper="已关闭 12 个" icon={FileClock} label="失败诊断" value="17" />
      </div>
      <PageToolbar placeholder="搜索报告、任务或失败原因" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">报告列表</h2>
              <p className="text-muted-foreground text-xs">运行记录、Allure 报告和失败诊断统一从这里进入。</p>
            </div>
            <Button variant="outline" size="sm">
              Allure 报告
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>报告编号</TableHead>
                  <TableHead>项目</TableHead>
                  <TableHead>报告名称</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id}>
                    <TableCell className="font-medium">{report.id}</TableCell>
                    <TableCell>{report.project}</TableCell>
                    <TableCell>{report.name}</TableCell>
                    <TableCell>
                      <Badge variant={report.status === "完成" ? "secondary" : "outline"}>{report.status}</Badge>
                    </TableCell>
                    <TableCell>{report.updated}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/reports">
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
              <StatusBadge>完成</StatusBadge>
              <span className="text-muted-foreground text-xs">项目维度与全局维度均可查看</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">报告中心</p>
              <p className="text-muted-foreground">报告页继续承载运行记录、Allure 报告与失败诊断列表。</p>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看失败诊断</Button>
              <Button variant="outline">打开运行记录</Button>
              <Button>刷新报告</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
