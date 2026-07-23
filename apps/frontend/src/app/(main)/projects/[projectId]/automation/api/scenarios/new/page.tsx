"use client";

import { useParams } from "next/navigation";

import { ApiScenarioEditor } from "@/components/ai-testing/api-automation/api-scenario-editor";
import { PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function NewApiScenarioPage() {
  const params = useParams<{ projectId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("apiAutomation", { label: "新建场景" })}
      description="组合接口用例、配置变量并定义执行顺序。"
      fillViewport
      projectScope="project"
      title="新建接口场景"
    >
      <ApiScenarioEditor projectId={params.projectId} />
    </PageShell>
  );
}
