import Link from "next/link";

import { ArrowRight, FolderPlus, NotebookTabs, Users } from "lucide-react";

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

const projects = [
  {
    id: "zhiliao",
    name: "知了平台",
    code: "ZL-001",
    status: "活跃",
    members: "18",
    updated: "2 小时前",
    assets: "需求 3 / 用例 426",
  },
  {
    id: "hawk",
    name: "鹰眼平台",
    code: "HK-002",
    status: "活跃",
    members: "12",
    updated: "1 天前",
    assets: "需求 2 / 用例 188",
  },
  {
    id: "atlas",
    name: "Atlas 内测",
    code: "AT-003",
    status: "归档",
    members: "6",
    updated: "8 天前",
    assets: "需求 1 / 用例 42",
  },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目工作区", "项目"]}
      description="管理项目、成员、环境配置和测试资产健康度。"
      primaryAction="新建项目"
      projectScope="all"
      tabs={["项目列表", "项目概览", "项目设置"]}
      title="项目"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="2 个归档项目" icon={NotebookTabs} label="活跃项目" value="4" />
        <MetricCard helper="测试工程师 12 人" icon={Users} label="项目成员" value="18" />
        <MetricCard helper="均已完成初始化" icon={FolderPlus} label="本周新增" value="2" />
      </div>
      <PageToolbar placeholder="搜索项目名称、编码或负责人" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">项目列表</h2>
              <p className="text-muted-foreground text-xs">项目列表、项目概览和项目设置统一从这里进入。</p>
            </div>
            <Button variant="outline" size="sm">
              新建项目
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>项目名称</TableHead>
                  <TableHead>项目编码</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>成员数</TableHead>
                  <TableHead>最近更新时间</TableHead>
                  <TableHead>资产摘要</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell className="font-medium">
                      <Link className="hover:underline" href={`/projects/${project.id}`}>
                        {project.name}
                      </Link>
                    </TableCell>
                    <TableCell>{project.code}</TableCell>
                    <TableCell>
                      <Badge variant={project.status === "归档" ? "outline" : "secondary"}>{project.status}</Badge>
                    </TableCell>
                    <TableCell>{project.members}</TableCell>
                    <TableCell>{project.updated}</TableCell>
                    <TableCell>{project.assets}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/projects/${project.id}`}>
                          进入
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
              <StatusBadge>活跃</StatusBadge>
              <span className="text-muted-foreground text-xs">当前项目：知了平台</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">项目控制台</p>
              <p className="text-muted-foreground">这里继续承载项目概览、成员管理、环境配置和项目设置入口。</p>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">进入当前项目</Button>
              <Button variant="outline">查看项目设置</Button>
              <Button>新建项目</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
