"use client";

import { useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { PageShell } from "@/components/ai-testing/page-shell";
import { PerformanceAnalysisReport } from "@/components/ai-testing/performance-testing/performance-analysis-report";
import { getPerformanceTest } from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

export default function Page() {
  const params = useParams<{
    projectId: string;
    testId: string;
    runId: string;
    analysisId: string;
  }>();
  const [testName, setTestName] = useState("");

  useEffect(() => {
    let cancelled = false;
    getPerformanceTest(params.projectId, params.testId)
      .then((performanceTest) => {
        if (!cancelled) setTestName(performanceTest.name);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [params.projectId, params.testId]);

  const reportBreadcrumbLabel = testName ? `${testName} - 性能智能分析报告` : "性能智能分析报告";

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("reports", { label: reportBreadcrumbLabel })}
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
