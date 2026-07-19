"use client";

import { useParams } from "next/navigation";

import { ApiRunDetail } from "@/components/ai-testing/api-automation/api-run-detail";

export default function Page() {
  const params = useParams<{ projectId: string; runId: string }>();
  return <ApiRunDetail projectId={params.projectId} runId={params.runId} />;
}
