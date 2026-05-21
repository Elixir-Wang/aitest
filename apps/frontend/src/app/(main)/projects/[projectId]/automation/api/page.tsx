"use client";

import { useParams } from "next/navigation";

import { PageShell, SoonPage } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectName = useProjectName(params.projectId);

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "接口自动化"]}
      description="第一版仅保留 pytest + requests + Allure 能力入口，不开放创建、生成或执行。"
      projectScope="project"
      tabs={["Soon 占位说明"]}
      title="接口自动化"
    >
      <SoonPage
        description="该模块在第一版只展示预留方向，当前不可创建任务、不可生成脚本、不可执行。"
        title="接口自动化暂未开放"
      />
    </PageShell>
  );
}
