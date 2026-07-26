"use client";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceAnalysisReport } from "@/components/ai-testing/performance-testing/performance-analysis-report";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{
    projectId: string;
    testId: string;
    runId: string;
    analysisId: string;
  }>();
  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("performanceTests", { label: "智能分析报告" })}
      description="查看性能目标、容量趋势、诊断证据与复测建议。"
      projectScope="project"
      title="性能智能分析报告"
    >
      <PerformanceAnalysisReport
        analysisId={params.analysisId}
        projectId={params.projectId}
        runId={params.runId}
        testId={params.testId}
      />
    </PageShell>
  );
}
