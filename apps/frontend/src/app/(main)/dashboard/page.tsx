import { AlertTriangle, CheckCircle2, Clock3, FolderKanban } from "lucide-react";

import { MetricCard, PageShell, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["工作台", "控制台"]}
      description="跨项目查看测试资产健康度、最近任务、待处理事项和质量风险。"
      projectScope="all"
      tabs={["全局概览", "待处理事项", "最近任务", "质量风险"]}
      title="控制台"
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard helper="4 个活跃项目" icon={FolderKanban} label="项目数" value="6" />
        <MetricCard helper="较上周 +6%" icon={CheckCircle2} label="用例采纳率" value="82%" />
        <MetricCard helper="3 个等待人工" icon={Clock3} label="运行中任务" value="12" />
        <MetricCard helper="2 个高风险" icon={AlertTriangle} label="失败待诊断" value="5" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">全局概览</h2>
              <p className="text-muted-foreground text-xs">所有数据受项目切换器范围约束。</p>
            </div>
            <Button variant="outline" size="sm">
              查看任务中心
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-muted-foreground text-xs">待处理事项</p>
                  <p className="mt-1 font-medium text-sm">3 个等待人工</p>
                </div>
                <StatusBadge>等待人工</StatusBadge>
              </div>
              <p className="mt-3 text-muted-foreground text-sm">需求评审 1，探索冲突 1，UI 诊断 1。</p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-muted-foreground text-xs">质量风险</p>
                  <p className="mt-1 font-medium text-sm">2 个高风险项</p>
                </div>
                <StatusBadge tone="muted">风险</StatusBadge>
              </div>
              <p className="mt-3 text-muted-foreground text-sm">主要集中在失败诊断和待确认冲突项。</p>
            </div>
          </div>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <h2 className="font-medium text-sm">最近任务</h2>
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span>需求分析 / 知了平台</span>
                <StatusBadge>运行中</StatusBadge>
              </div>
              <div className="flex items-center justify-between">
                <span>用例生成 / 鹰眼平台</span>
                <StatusBadge>成功</StatusBadge>
              </div>
              <div className="flex items-center justify-between">
                <span>UI 自动化 / 知了平台</span>
                <StatusBadge tone="muted">失败</StatusBadge>
              </div>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
