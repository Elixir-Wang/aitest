"use client";

import { ExplorationWorkspace } from "@/components/ai-testing/exploration-workspace";

export default function Page() {
  return (
    <ExplorationWorkspace
      breadcrumbs={["项目工作区", "探索"]}
      description="查看全部项目的探索任务、页面事实和冲突项。"
      projectScope="all"
      title="探索"
    />
  );
}
