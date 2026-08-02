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

export type ApiScenarioRequestField = {
  key: string;
  location: string;
  target: string;
  required: boolean;
  description: string;
  schema: Record<string, unknown>;
  defaultValue?: unknown;
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

export function normalizeRequestLifecycleConfig(step: ApiAutomationScenarioStep): Record<string, unknown> & {
  timeout_ms: number;
  retries: number;
  retry_interval_ms: number;
  pre_request: { actions: Array<Record<string, unknown>>; script: string };
  post_response: { actions: Array<Record<string, unknown>>; script: string };
};

export function formatValueSource(
  source: ApiAutomationScenarioStep["bindings"][number]["source"],
  stepName?: string,
): string;

export function buildEndpointRequestFields(endpoint: ApiAutomationEndpoint): {
  bodyMode: string;
  mediaType: string;
  fields: ApiScenarioRequestField[];
};

export function resolveRequestFieldValue(
  requestOverrides: Record<string, unknown>,
  target: string,
  defaultValue?: unknown,
): unknown;

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
