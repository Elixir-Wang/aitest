import { PlaySquare } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "UI 自动化"]}
      description="基于 pytest + Playwright + Allure 生成、查看、执行和诊断 UI 自动化。"
      primaryAction="生成自动化"
      projectScope="project"
      tabs={["套件列表", "代码查看", "本地执行", "Allure 报告", "失败诊断"]}
      title="UI 自动化"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="可执行 15 个" icon={PlaySquare} label="自动化套件" value="18" />
        <MetricCard helper="失败 7 条" icon={PlaySquare} label="最近通过率" value="88%" />
        <MetricCard helper="需人工启用自愈" icon={PlaySquare} label="待诊断" value="5" />
      </div>
      <PageToolbar placeholder="搜索套件、用例或执行记录" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <h2 className="font-medium text-sm">自动化套件列表</h2>
          <p className="mt-2 text-muted-foreground text-sm">
            后续将补齐套件表格、代码查看、本地执行、Allure 报告入口和失败诊断详情。
          </p>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>运行中</StatusBadge>
              <span className="text-muted-foreground text-xs">本地执行器可用</span>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">查看代码</Button>
              <Button variant="outline">查看 Allure</Button>
              <Button>生成自动化</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
