import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "新建性能测试" })}
      description="定义单接口场景、负载窗口、质量门禁与安全熔断。"
      projectScope="project"
      title="新建托管性能场景"
    >
      <PerformanceTestForm />
    </PageShell>
  );
}
