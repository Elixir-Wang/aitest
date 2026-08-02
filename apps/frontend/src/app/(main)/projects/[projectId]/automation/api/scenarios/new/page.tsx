import { redirect } from "next/navigation";

export default async function NewApiScenarioPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/automation/api?tab=scenarios`);
}
