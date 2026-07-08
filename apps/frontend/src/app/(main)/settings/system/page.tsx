import { PageShell, SoonPage } from "@/components/ai-testing/page-shell";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={[{ label: "系统管理" }, { label: "系统设置" }]}
      description="系统设置暂不开放。"
      projectScope="none"
      title="系统设置"
    >
      <SoonPage description="系统设置将在接入真实存储、Runner、Allure 和安全策略后开放。" title="系统设置" />
    </PageShell>
  );
}
