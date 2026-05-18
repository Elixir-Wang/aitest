import Link from "next/link";

import { ArrowRight, FileText, GitBranch, ListChecks } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const requirements = [
  { id: "req-001", title: "登录与权限", status: "待评审", version: "v3", owner: "张敏", updated: "2 小时前" },
  { id: "req-002", title: "项目管理", status: "已确认", version: "v2", owner: "李强", updated: "6 小时前" },
  { id: "req-003", title: "报告中心", status: "待澄清", version: "v1", owner: "王磊", updated: "1 天前" },
];

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "需求"]}
      description="上传、预览、编辑需求文档，并进行 AI 分析、模块评审和澄清写回。"
      primaryAction="上传需求"
      projectScope="project"
      tabs={["文档管理", "需求评审", "分析结果", "澄清问题", "版本记录"]}
      title="需求"
      >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="1 份等待澄清" icon={FileText} label="需求文档" value="3" />
        <MetricCard helper="已确认 9 个" icon={FileText} label="模块覆盖" value="12" />
        <MetricCard helper="最近更新 2 小时前" icon={FileText} label="版本记录" value="8" />
      </div>
      <PageToolbar placeholder="搜索需求文档、模块或状态" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">需求文档列表</h2>
              <p className="text-muted-foreground text-xs">文档预览、澄清写回和版本评审统一在此入口。</p>
            </div>
            <Button variant="outline" size="sm">
              文档管理
            </Button>
          </div>
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>需求编号</TableHead>
                  <TableHead>需求标题</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>版本</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requirements.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.id}</TableCell>
                    <TableCell>{item.title}</TableCell>
                    <TableCell>
                      <Badge variant={item.status === "已确认" ? "secondary" : "outline"}>{item.status}</Badge>
                    </TableCell>
                    <TableCell>{item.version}</TableCell>
                    <TableCell>{item.owner}</TableCell>
                    <TableCell>{item.updated}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link href="/projects/zhiliao/requirements">
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
              <StatusBadge>待评审</StatusBadge>
              <span className="text-muted-foreground text-xs">当前版本 v3</span>
            </div>
            <div className="mt-3 space-y-3 text-sm">
              <p className="font-medium">登录与权限</p>
              <p className="text-muted-foreground">展示需求原文、AI 结构化拆解、评审意见和澄清写回。</p>
              <div className="grid gap-2 text-muted-foreground text-xs">
                <div className="flex items-center gap-2">
                  <ListChecks className="size-4" />
                  <span>已拆分 6 个功能点</span>
                </div>
                <div className="flex items-center gap-2">
                  <GitBranch className="size-4" />
                  <span>存在 2 条待确认冲突</span>
                </div>
              </div>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">可用操作</h2>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">预览差异</Button>
              <Button variant="outline">进入评审</Button>
              <Button>上传需求</Button>
            </div>
          </ShellSection>
          <ShellSection>
            <h2 className="font-medium text-sm">来源与版本</h2>
            <div className="mt-3 space-y-2 text-muted-foreground text-sm">
              <p>来源：PRD 文档 / 登录权限章节</p>
              <p>版本：v3，较 v2 新增 2 个约束</p>
              <p>关联任务：需求分析 t-1001</p>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
