import { SoonPage, PageShell } from "@/components/ai-testing/page-shell";

export default function Page() {
  return (
    <PageShell
      breadcrumbs={["项目", "知了平台", "接口自动化"]}
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
