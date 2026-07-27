import { PageShell } from "@/components/ai-testing/page-shell";
import { SiliconOfficeDashboard } from "@/components/ai-testing/silicon-office/office-dashboard";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function SiliconEmployeesPage() {
  return (
    <PageShell breadcrumbs={moduleBreadcrumbs("agents")} fillViewport projectScope="all" title="硅基员工">
      <SiliconOfficeDashboard embedded />
    </PageShell>
  );
}
