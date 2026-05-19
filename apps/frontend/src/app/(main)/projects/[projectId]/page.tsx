import { FolderKanban, Users, Workflow } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={[]}
      description=""
      primaryAction="编辑项目"
      projectScope="project"
      activeTab="项目概览"
      tabs={[
        { label: "项目概览", href: "/projects/zhiliao" },
        { label: "项目设置", href: "/projects/zhiliao/settings" },
        "成员",
        "环境配置",
      ]}
      title="知了平台"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="当前启用" icon={FolderKanban} label="项目状态" value="活跃" />
        <MetricCard helper="12 位成员" icon={Users} label="项目成员" value="18" />
        <MetricCard helper="资产健康" icon={Workflow} label="测试资产" value="良好" />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">需求 3</Badge>
        <Badge variant="secondary">用例 426</Badge>
        <Badge variant="secondary">UI 自动化 18</Badge>
        <Badge variant="outline">最近更新 2026-05-19 12:30:00</Badge>
      </div>
      <PageToolbar placeholder="搜索项目成员、配置或资产" />
      <div className="grid gap-4 lg:grid-cols-3">
        <ShellSection className="lg:col-span-2">
          <h2 className="mb-3 font-medium text-sm">项目概览</h2>
          <div className="space-y-3 text-sm">
            <p>项目编码：ZL-001</p>
            <p>负责人：张敏</p>
            <p>环境：测试 / 预发 / 生产</p>
            <p>说明：用于承载 PRD 指定的需求、探索、知识库和测试资产链路。</p>
          </div>
        </ShellSection>
        <ShellSection>
          <h2 className="mb-3 font-medium text-sm">可用操作</h2>
          <div className="flex flex-col gap-2">
            <Button variant="outline">进入需求</Button>
            <Button variant="outline">进入探索</Button>
            <Button variant="outline">管理成员</Button>
            <Button>编辑项目</Button>
          </div>
        </ShellSection>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ShellSection className="lg:col-span-2">
          <div className="flex items-center gap-2">
            <StatusBadge>活跃</StatusBadge>
            <span className="text-muted-foreground text-xs">项目上下文已启用</span>
          </div>
          <p className="mt-3 text-muted-foreground text-sm">后续这里会继续承载成员、环境配置和资产健康度的细分内容。</p>
        </ShellSection>
      </div>
    </PageShell>
  );
}
