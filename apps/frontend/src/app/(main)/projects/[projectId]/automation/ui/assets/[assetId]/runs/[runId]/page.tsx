"use client";

import { useParams } from "next/navigation";

import { UiAutomationRunDetail } from "@/components/ai-testing/ui-automation/ui-automation-run-detail";

export default function Page() {
  const params = useParams<{ projectId: string; assetId: string; runId: string }>();
  return <UiAutomationRunDetail assetId={params.assetId} projectId={params.projectId} runId={params.runId} />;
}
