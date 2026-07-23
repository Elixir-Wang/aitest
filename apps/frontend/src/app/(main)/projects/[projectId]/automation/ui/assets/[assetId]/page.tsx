"use client";

import { useParams } from "next/navigation";

import { UiAutomationAssetDetail } from "@/components/ai-testing/ui-automation/ui-automation-asset-detail";

export default function Page() {
  const params = useParams<{ projectId: string; assetId: string }>();
  return <UiAutomationAssetDetail assetId={params.assetId} projectId={params.projectId} />;
}
