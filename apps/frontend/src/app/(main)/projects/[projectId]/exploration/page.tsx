import Link from "next/link";

import { ArrowRight, FileSearch, MapPinned, ScanLine } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const explorations = [
  { id: "exp-001", title: "登录流程探索", status: "运行中", site: "官网", owner: "张敏", updated: "12 分钟前" },
  { id: "exp-002", title: "项目管理探索", status: "完成", site: "管理台", owner: "李强", updated: "4 小时前" },
  { id: "exp-003", title: "报告中心探索", status: "待确认", site: "报告台", owner: "王磊", updated: "1 天前" },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "探索"]}
      description="配置站点探索任务，沉淀页面事实、探索文档、候选需求和冲突项。"
      primaryAction="开始探索"
      projectScope="project"
      tabs={["站点配置", "探索任务", "探索文档", "候选需求文档", "冲突项"]}
      title="探索"
      >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="1 个运行中" icon={FileSearch} label="探索任务" value="7" />
        <MetricCard helper="覆盖 12 个流程" icon={FileSearch} label="页面事实" value="86" />
        <MetricCard helper="2 个等待确认" icon={FileSearch} label="冲突项" value="4" />
      </div>
      <PageToolbar placeholder="搜索探索任务、页面或冲突项" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">探索任务列表</h2>
              <p className="text-muted-foreground text-xs">用于记录站点探索过程、页面事实和冲突项。</p>
            </div>
            <Button variant="outline" size="sm">
              站点配置
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>探索编号</TableHead>
                  <TableHead>探索标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>站点</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {explorations.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.id}</TableCell>
                    <TableCell>{item.title}</TableCell>
                    <TableCell>
                      <Badge variant={item.status === "完成" ? "secondary" : "outline"}>{item.status}</Badge>
                    </TableCell>
                    <TableCell>{item.site}</TableCell>
                    <TableCell>{item.owner}</TableCell>
                    <TableCell>{item.updated}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/projects/zhiliao/exploration">
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
              <StatusBadge>运行中</StatusBadge>
              <span className="text-muted-foreground text-xs">站点：官网</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">登录流程探索</p>
              <p className="text-muted-foreground">探索结果会沉淀页面事实、候选需求和截图来源。</p>
              <div className="grid gap-2 text-muted-foreground text-xs">
                <div className="flex items-center gap-2">
                  <ScanLine className="size-4" />
                  <span>已发现 18 个页面事实</span>
                </div>
                <div className="flex items-center gap-2">
                  <MapPinned className="size-4" />
                  <span>3 个冲突项等待确认</span>
                </div>
              </div>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看探索文档</Button>
              <Button variant="outline">处理冲突项</Button>
              <Button>开始探索</Button>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">运行摘要</h2>
            <div className="mt-3 space-y-2 text-muted-foreground text-sm">
              <p>阶段：登录、项目切换、报告查看</p>
              <p>证据：截图 12 张，trace 3 份</p>
              <p>关联任务：探索任务 t-1002</p>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
