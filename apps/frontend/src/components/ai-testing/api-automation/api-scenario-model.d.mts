import type {
  ApiAutomationEndpoint,
  ApiAutomationScenarioStep,
  ApiAutomationScenarioStepInput,
} from "@/lib/api-client";

export type ApiScenarioVariableOptions = {
  stepOutputs: Array<{ stepId: string; stepName: string; name: string }>;
  scenarioVariables: string[];
  environmentVariables: string[];
};

export function createEndpointStep(
  endpoint: Pick<ApiAutomationEndpoint, "id" | "method" | "path" | "summary">,
  projectId: string,
  scenarioId?: string,
  stepId?: string,
): ApiAutomationScenarioStep;

export function createUtilityStep(
  stepType: Exclude<ApiAutomationScenarioStep["step_type"], "api_request">,
  projectId: string,
  scenarioId?: string,
  stepId?: string,
): ApiAutomationScenarioStep;

export function moveScenarioStep(
  steps: ApiAutomationScenarioStep[],
  activeId: string,
  overId: string,
): ApiAutomationScenarioStep[];

export function toScenarioStepInput(step: ApiAutomationScenarioStep, stepOrder: number): ApiAutomationScenarioStepInput;

export function buildVariableOptions(
  steps: ApiAutomationScenarioStep[],
  activeStepId: string,
  scenarioVariables?: Record<string, unknown>,
  environmentVariables?: Record<string, unknown>,
): ApiScenarioVariableOptions;

export function validateScenarioDraft(draft: { name: string; steps: ApiAutomationScenarioStep[] }): {
  valid: boolean;
  errors: string[];
  warnings: string[];
};
