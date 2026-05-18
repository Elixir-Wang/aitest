import Link from "next/link";

import { ArrowRight, DatabaseZap, Files, LibraryBig } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const knowledge = [
  { id: "kb-001", title: "登录与权限知识块", status: "已发布", source: "需求 + 探索", owner: "张敏", updated: "2 小时前" },
  { id: "kb-002", title: "项目管理知识块", status: "待更新", source: "需求", owner: "李强", updated: "6 小时前" },
  { id: "kb-003", title: "报告中心知识块", status: "已发布", source: "探索", owner: "王磊", updated: "1 天前" },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "知识库"]}
      description="基于需求和探索来源生成 llm-wiki 风格知识库，并追踪来源和版本。"
      primaryAction="生成知识库"
      projectScope="project"
      tabs={["知识库首页", "来源材料", "模块文档", "更新预览", "历史版本"]}
      title="知识库"
      >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="12 个已发布" icon={DatabaseZap} label="模块文档" value="14" />
        <MetricCard helper="需求与探索融合" icon={DatabaseZap} label="来源引用" value="238" />
        <MetricCard helper="需人工确认" icon={DatabaseZap} label="待更新" value="3" />
      </div>
      <PageToolbar placeholder="搜索模块、来源或版本" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">知识库列表</h2>
              <p className="text-muted-foreground text-xs">展示模块文档、来源材料和历史版本的统一入口。</p>
            </div>
            <Button variant="outline" size="sm">
              来源材料
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>模块编号</TableHead>
                  <TableHead>模块标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>来源</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {knowledge.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.id}</TableCell>
                    <TableCell>{item.title}</TableCell>
                    <TableCell>
                      <Badge variant={item.status === "已发布" ? "secondary" : "outline"}>{item.status}</Badge>
                    </TableCell>
                    <TableCell>{item.source}</TableCell>
                    <TableCell>{item.owner}</TableCell>
                    <TableCell>{item.updated}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/projects/zhiliao/knowledge">
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
              <StatusBadge>已发布</StatusBadge>
              <span className="text-muted-foreground text-xs">来源：需求 + 探索</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">登录与权限知识块</p>
              <p className="text-muted-foreground">知识库会把来源、更新预览和历史版本统一收拢。</p>
              <div className="grid gap-2 text-muted-foreground text-xs">
                <div className="flex items-center gap-2">
                  <LibraryBig className="size-4" />
                  <span>12 个模块文档已发布</span>
                </div>
                <div className="flex items-center gap-2">
                  <Files className="size-4" />
                  <span>238 条来源引用可追溯</span>
                </div>
              </div>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看历史版本</Button>
              <Button variant="outline">更新预览</Button>
              <Button>生成知识库</Button>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">来源追踪</h2>
            <div className="mt-3 space-y-2 text-muted-foreground text-sm">
              <p>需求来源：登录与权限 v3</p>
              <p>探索来源：登录流程探索 exp-001</p>
              <p>最近发布：2 小时前</p>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
