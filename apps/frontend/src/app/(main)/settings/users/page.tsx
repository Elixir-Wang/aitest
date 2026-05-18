import { Users } from "lucide-react";

import { MetricCard, PageShell, PageToolbar, ShellSection, StatusBadge } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["系统管理", "用户与权限"]}
      description="管理管理员、测试工程师、访客账号和项目分配。"
      primaryAction="新增用户"
      projectScope="none"
      tabs={["用户管理", "项目分配", "个人配置"]}
      title="用户与权限"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="管理员 3 人" icon={Users} label="用户总数" value="24" />
        <MetricCard helper="12 人已分配项目" icon={Users} label="测试工程师" value="16" />
        <MetricCard helper="全部只读" icon={Users} label="访客" value="5" />
      </div>
      <PageToolbar placeholder="搜索用户、角色或项目" />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <ShellSection>
          <h2 className="font-medium text-sm">用户与权限列表</h2>
          <p className="mt-2 text-muted-foreground text-sm">
            第一版不开放注册，账号由管理员创建，并按项目分配可见和可写范围。
          </p>
        </ShellSection>
        <div className="space-y-4">
          <ShellSection>
            <div className="flex items-center gap-2">
              <StatusBadge>只读</StatusBadge>
              <span className="text-muted-foreground text-xs">访客不可写</span>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <Button variant="outline">项目分配</Button>
              <Button variant="outline">个人配置</Button>
              <Button>新增用户</Button>
            </div>
          </ShellSection>
        </div>
      </div>
    </PageShell>
  );
}
