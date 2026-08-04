import { PerformanceTestForm } from "@/components/ai-testing/performance-testing/performance-test-form";

export default async function EditPerformanceTestPage({
  params,
}: {
  params: Promise<{ projectId: string; testId: string }>;
}) {
  const { projectId, testId } = await params;
  return <PerformanceTestForm editTestId={testId} projectIdForEdit={projectId} />;
}
