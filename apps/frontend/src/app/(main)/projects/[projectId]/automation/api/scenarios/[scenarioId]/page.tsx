"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function EditApiScenarioPage() {
  const params = useParams<{ projectId: string; scenarioId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("apiAutomation", { label: "编辑场景" })}
      description="维护场景步骤、变量、版本记录和运行配置。"
      fillViewport
      projectScope="project"
      title="编辑接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} scenarioId={params.scenarioId} />
    </PageShell>
  );
}
