"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { ScriptReview } from "@/components/ai-testing/performance-testing/script-review";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{ projectId: string; testId: string; scriptId: string }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "performanceTests",
        { label: "性能测试列表", href: `/projects/${params.projectId}/performance-tests` },
        { label: "脚本审核" },
      )}
      description="审核结构化请求配置、校验结果和只读 Locust 脚本。"
      projectScope="project"
      title="Locust 脚本审核"
    >
      <ScriptReview projectId={params.projectId} scriptId={params.scriptId} testId={params.testId} />
    </PageShell>
  );
}
