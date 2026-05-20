"use client";

import { useParams, useRouter } from "next/navigation";

import { ClipboardCheck, FileText, PlaySquare } from "lucide-react";

import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { projectOptions } from "@/stores/project-context-store";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const router = useRouter();
  const selectProject = useProjectContextStore((state) => state.selectProject);
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const projectName = projectOptions.find((item) => item.id === projectId)?.name ?? "项目";

  function goToModule(modulePath: string) {
    selectProject(projectId);
    router.push(`/projects/${projectId}/${modulePath}`);
  }

  return (
    <PageShell
      breadcrumbs={[]}
      description=""
      primaryAction="编辑项目"
      projectScope="project"
      title={projectName}
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="已确认 9 个模块" icon={FileText} label="需求数" value="3" />
        <MetricCard helper="已采纳 351 条" icon={ClipboardCheck} label="用例数" value="426" />
        <MetricCard helper="可执行 15 个" icon={PlaySquare} label="UI 自动化数量" value="18" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ShellSection className="lg:col-span-2">
          <h2 className="mb-3 font-medium text-sm">项目概览</h2>
          <div className="space-y-3 text-sm">
            <p>项目编码：ZL-001</p>
            <p>负责人：张敏</p>
            <p>说明：用于承载 PRD 指定的需求、探索、知识库和测试资产链路。</p>
          </div>
        </ShellSection>
        <ShellSection>
          <h2 className="mb-3 font-medium text-sm">可用操作</h2>
          <div className="flex flex-col gap-2">
            <Button variant="outline" onClick={() => goToModule("requirements")}>
              进入需求
            </Button>
            <Button variant="outline" onClick={() => goToModule("exploration")}>
              进入探索
            </Button>
            <Button onClick={() => goToModule("test-cases")}>进入测试用例</Button>
          </div>
        </ShellSection>
      </div>
    </PageShell>
  );
}
