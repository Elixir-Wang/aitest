import { Settings } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["系统管理", "系统设置"]}
      description="配置文件存储、本地 Runner、Playwright、Allure 和 Agent 安全策略。"
      projectScope="none"
      tabs={["文件存储", "本地 Runner", "Playwright", "Allure", "Agent 安全策略"]}
      title="系统设置"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="待接入健康检查" icon={Settings} label="Runner" value="本地" />
        <MetricCard helper="用于探索和 UI 自动化" icon={Settings} label="Playwright" value="预留" />
        <MetricCard helper="用于报告跳转" icon={Settings} label="Allure" value="预留" />
      </div>
      <PageToolbar placeholder="搜索配置项或运行状态" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <h2 className="font-medium text-sm">系统设置列表</h2>
          <p className="mt-2 text-muted-foreground text-sm">
            后续将补齐存储路径、本地执行器、Playwright、Allure 和安全策略配置。
          </p>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>Soon</StatusBadge>
              <span className="text-muted-foreground text-xs">核心配置后续开放</span>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看存储</Button>
              <Button variant="outline">查看 Runner</Button>
              <Button>保存配置</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
