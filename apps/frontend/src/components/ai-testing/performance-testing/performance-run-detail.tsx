"use client";

import { LocustConsole } from "./locust-console";

export function PerformanceRunDetail({
  projectId,
  testId,
  runId,
}: {
  projectId: string;
  testId: string;
  runId: string;
}) {
  return <LocustConsole projectId={projectId} runId={runId} testId={testId} />;
}
