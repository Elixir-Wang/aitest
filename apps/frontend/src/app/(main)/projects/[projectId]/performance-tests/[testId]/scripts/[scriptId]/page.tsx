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
        { label: "脚本配置" },
      )}
      description="调整结构化请求配置并查看生成的 Locust 脚本。"
      projectScope="project"
      title="Locust 脚本配置"
    >
      <ScriptReview projectId={params.projectId} scriptId={params.scriptId} testId={params.testId} />
    </PageShell>
  );
}
