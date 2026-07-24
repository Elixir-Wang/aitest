import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "新建性能测试" })}
      description="创建单接口托管场景，预热流量不会计入质量门禁。"
      projectScope="all"
      title="新建托管性能场景"
    >
      <PerformanceTestForm />
    </PageShell>
  );
}
