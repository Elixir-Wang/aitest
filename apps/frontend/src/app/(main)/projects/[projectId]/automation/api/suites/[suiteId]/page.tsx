"use client";

import { useParams } from "next/navigation";

import { ApiScenarioSuiteDetail } from "@/components/ai-testing/api-automation/api-scenario-suite-detail";
import { PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function ApiScenarioSuiteDetailPage() {
  const params = useParams<{ projectId: string; suiteId: string }>();

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "apiAutomation",
        {
          label: "批量运行",
          href: `/projects/${params.projectId}/automation/api?tab=batch-runs`,
        },
        { label: "测试集详情" },
      )}
      description="查看测试集配置、场景执行顺序和最近运行结果。"
      projectScope="project"
      title="测试集详情"
    >
      <ApiScenarioSuiteDetail projectId={params.projectId} suiteId={params.suiteId} />
    </PageShell>
  );
}
