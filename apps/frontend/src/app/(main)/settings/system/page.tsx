import { PageShell, SoonPage } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("systemSettings")}
      description="系统设置暂不开放。"
      projectScope="none"
      title="系统设置"
    >
      <SoonPage description="系统设置将在接入真实存储、Runner、Allure 和安全策略后开放。" title="系统设置" />
    </PageShell>
  );
}
