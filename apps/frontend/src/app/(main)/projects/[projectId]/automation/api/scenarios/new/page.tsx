"use client";

import { useParams } from "next/navigation";

import { ApiScenarioCreateForm } from "@/components/ai-testing/api-automation/api-scenario-create-form";
import { PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function NewApiScenarioPage() {
  const params = useParams<{ projectId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("apiAutomation", { label: "新建场景" })}
      projectScope="project"
      title="新建场景"
    >
      <ApiScenarioCreateForm projectId={params.projectId} />
    </PageShell>
  );
}
