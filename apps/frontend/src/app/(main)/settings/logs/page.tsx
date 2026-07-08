import { OperationLogView } from "@/components/ai-testing/operation-logs/operation-log-view";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={[{ label: "系统管理" }, { label: "系统日志" }]}
      description="查看系统级操作审计、配置变更、任务生命周期和 Agent 调用摘要。"
      projectScope="none"
      title="系统日志"
    >
      <ShellSection>
        <OperationLogView endpoint="/operation-logs" showProjectFilter />
      </ShellSection>
    </PageShell>
  );
}
