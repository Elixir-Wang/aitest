import type { ApiAutomationEndpoint, ApiScenarioAiPlan } from "@/lib/api-client";

export type AiPlanParameterView = {
  key: string;
  name: string;
  location: string;
  source: string;
  value: string;
  rawTarget: unknown;
  rawSource: unknown;
};

export type AiPlanPresentation = {
  goal: string;
  steps: Array<{
    id: string;
    index: number;
    name: string;
    purpose: string;
    method: string;
    path: string;
    phase: string;
    parameters: AiPlanParameterView[];
    dependencies: Array<{
      stepId: string;
      stepName: string;
      variable?: string;
      target: string;
    }>;
    rawNode: ApiScenarioAiPlan["nodes"][number];
  }>;
  commonParameters: Array<AiPlanParameterView & { usedBy: string[] }>;
  actionItems: Array<{
    name: string;
    label: string;
    description: string;
    value: string;
    targets: string[];
  }>;
  diagnostics: string[];
};

export function buildAiPlanPresentation(
  plan: ApiScenarioAiPlan,
  endpoints: ApiAutomationEndpoint[],
  submittedGoal?: string,
): AiPlanPresentation;
