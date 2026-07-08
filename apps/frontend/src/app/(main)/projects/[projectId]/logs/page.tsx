"use client";

import { useParams } from "next/navigation";

import { OperationLogView } from "@/components/ai-testing/operation-logs/operation-log-view";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={[
        { label: "项目工作区" },
        { label: "项目", href: "/projects" },
        { label: projectName, href: `/projects/${params.projectId}` },
        { label: "项目日志" },
      ]}
      description="查看当前项目内的需求、探索、测试资产、任务和报告相关操作日志。"
      projectScope="project"
      title="项目日志"
    >
      <ShellSection>
        <OperationLogView endpoint={`/projects/${params.projectId}/operation-logs`} />
      </ShellSection>
    </PageShell>
  );
}
