import { Bot } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["系统管理", "模型配置"]}
      description="管理 Provider、模型用途、Agent 模型策略和安全边界。"
      primaryAction="新增 Provider"
      projectScope="none"
      tabs={["Provider", "模型用途", "Agent 模型策略"]}
      title="模型配置"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="2 个可用" icon={Bot} label="Provider" value="3" />
        <MetricCard helper="覆盖核心任务" icon={Bot} label="模型用途" value="8" />
        <MetricCard helper="需管理员维护" icon={Bot} label="安全策略" value="4" />
      </div>
      <PageToolbar placeholder="搜索 Provider、模型或用途" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <h2 className="font-medium text-sm">模型配置列表</h2>
          <p className="mt-2 text-muted-foreground text-sm">
            后续将补齐 Provider 表单、用途映射、Agent Runtime 策略和可用性检查。
          </p>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>待接入</StatusBadge>
              <span className="text-muted-foreground text-xs">当前仅保留壳层</span>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看用途</Button>
              <Button variant="outline">查看策略</Button>
              <Button>新增 Provider</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
