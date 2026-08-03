"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioRevision,
  type ApiAutomationScenarioRunResult,
  type ApiAutomationScenarioStep,
  type ApiScenarioAiPlanAccepted,
  type ApiScenarioAiPlanValueSource,
  type ApiScenarioAiReviewPlan,
  type ApiScenarioAiReviewStep,
  applyApiScenarioAiPlan,
  createApiAutomationScenario,
  createApiScenarioAiPlan,
  executeApiAutomationScenario,
  getApiAutomationRun,
  getApiAutomationScenario,
  getApiAutomationScenarioRunResult,
  getApiScenarioAiPlan,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  listApiAutomationScenarioRevisions,
  restoreApiAutomationScenarioRevision,
  saveApiAutomationScenarioVersion,
  saveApiScenarioAiPlanReview,
  updateApiAutomationScenario,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import {
  createEndpointStep,
  createUtilityStep,
  moveScenarioStep,
  toScenarioStepInput,
  validateScenarioDraft,
} from "./api-scenario-model.mjs";

type ScenarioDraft = {
  name: string;
  description: string;
  variables: Record<string, unknown>;
  steps: ApiAutomationScenarioStep[];
};

const emptyDraft: ScenarioDraft = { name: "", description: "", variables: {}, steps: [] };

function pointerParts(path: string) {
  return path
    .split("/")
    .slice(1)
    .map((part) => part.replaceAll("~1", "/").replaceAll("~0", "~"));
}

function isDescendantPath(path: string, parentPath: string) {
  return path.startsWith(`${parentPath}/`);
}

function nestedSource(source: ApiScenarioAiPlanValueSource, relativePath: string): ApiScenarioAiPlanValueSource | null {
  let current: ApiScenarioAiPlanValueSource | undefined = source;
  for (const part of pointerParts(relativePath)) {
    current = current?.type === "object" ? current.properties?.[part] : undefined;
  }
  return current ?? null;
}

function setNestedSource(
  source: ApiScenarioAiPlanValueSource,
  relativePath: string,
  value: ApiScenarioAiPlanValueSource,
) {
  const next = structuredClone(source);
  if (next.type !== "object") return next;
  const properties = next.properties ?? {};
  next.properties = properties;
  let current: { type: "object"; properties: Record<string, ApiScenarioAiPlanValueSource> } = {
    type: "object",
    properties,
  };
  for (const part of pointerParts(relativePath).slice(0, -1)) {
    const child = current.properties[part];
    if (child?.type !== "object") current.properties[part] = { type: "object", properties: {} };
    current = current.properties[part] as { type: "object"; properties: Record<string, ApiScenarioAiPlanValueSource> };
  }
  const leaf = pointerParts(relativePath).at(-1);
  if (leaf) current.properties[leaf] = value;
  return next;
}

function synchronizeReviewField(
  step: ApiScenarioAiReviewStep,
  fieldId: string,
  resolved: ApiScenarioAiPlanValueSource,
  status: "pending" | "resolved" | "confirmed",
): ApiScenarioAiReviewStep {
  const fields = step.field_groups.flatMap((group) => group.fields);
  const target = fields.find((field) => field.field_id === fieldId);
  if (!target) return step;

  let nextFields = fields.map((field) => (field.field_id === fieldId ? { ...field, resolved, status } : field));
  const parent = fields
    .filter((field) => {
      const parentSource = field.resolved ?? field.proposal;
      return (
        parentSource.type === "object" &&
        field.path !== target.path &&
        field.path.startsWith(`${target.path}/`) === false &&
        isDescendantPath(target.path, field.path)
      );
    })
    .sort((left, right) => right.path.length - left.path.length)[0];

  if (parent) {
    const parentSource = parent.resolved ?? parent.proposal;
    const relativePath = target.path.slice(parent.path.length);
    const nextParentSource = setNestedSource(parentSource, relativePath, resolved);
    const descendants = fields.filter(
      (field) => field.field_id !== parent.field_id && isDescendantPath(field.path, parent.path),
    );
    const nextDescendants = nextFields.filter((field) => descendants.some((item) => item.field_id === field.field_id));
    const parentStatus = nextDescendants.every((field) => field.status === "confirmed")
      ? "confirmed"
      : nextDescendants.every((field) => field.status !== "pending")
        ? "resolved"
        : "pending";
    nextFields = nextFields.map((field) =>
      field.field_id === parent.field_id ? { ...field, resolved: nextParentSource, status: parentStatus } : field,
    );
  } else if (resolved.type === "object") {
    const descendants = fields.filter(
      (field) => field.field_id !== target.field_id && isDescendantPath(field.path, target.path),
    );
    nextFields = nextFields.map((field) => {
      if (!descendants.some((item) => item.field_id === field.field_id)) return field;
      const child = nestedSource(resolved, field.path.slice(target.path.length));
      return child ? { ...field, resolved: child, status } : field;
    });
  }

  return {
    ...step,
    field_groups: step.field_groups.map((group) => ({
      ...group,
      fields: group.fields.map((field) => nextFields.find((item) => item.field_id === field.field_id) ?? field),
    })),
  };
}

function synchronizeConfirmedObjectFields(step: ApiScenarioAiReviewStep) {
  return step.field_groups
    .flatMap((group) => group.fields)
    .filter((field) => field.status !== "pending" && (field.resolved ?? field.proposal).type === "object")
    .reduce(
      (current, field) =>
        synchronizeReviewField(current, field.field_id, field.resolved ?? field.proposal, field.status),
      step,
    );
}

function summarizeAiReviewPlan(plan: ApiScenarioAiReviewPlan): ApiScenarioAiReviewPlan {
  const steps = [...plan.steps]
    .sort((left, right) => left.order - right.order)
    .map((rawStep, index) => {
      const step = synchronizeConfirmedObjectFields(rawStep);
      const fieldGroups = step.field_groups.map((group) => ({
        ...group,
        pending_count: group.fields.filter((field) => field.status === "pending").length,
      }));
      const fields = fieldGroups.flatMap((group) => group.fields);
      return {
        ...step,
        order: index + 1,
        field_groups: fieldGroups,
        review_summary: {
          ...step.review_summary,
          pending_count: fields.filter((field) => field.status === "pending").length,
          resolved_count: fields.filter((field) => field.status !== "pending").length,
        },
      };
    });
  const pendingCount = steps.reduce((total, step) => total + step.review_summary.pending_count, 0);
  const blockingCount = steps.reduce((total, step) => total + step.review_summary.blocking_count, 0);
  return {
    ...plan,
    steps,
    review_status: pendingCount === 0 && blockingCount === 0 && plan.validation.valid ? "ready" : "pending",
  };
}

function aiPlanStorageKey(projectId: string, scenarioId: string) {
  return `api-scenario-ai-plan:${projectId}:${scenarioId}`;
}

export function useApiScenarioEditor(projectId: string, scenarioId?: string) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialEnvironmentId = searchParams.get("environmentId") ?? "";
  const [scenario, setScenario] = useState<ApiAutomationScenario | null>(null);
  const [draft, setDraft] = useState<ScenarioDraft>(emptyDraft);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [environmentSaving, setEnvironmentSaving] = useState(false);
  const [activeStepId, setActiveStepId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [latestRunId, setLatestRunId] = useState("");
  const [revisions, setRevisions] = useState<ApiAutomationScenarioRevision[]>([]);
  const [latestRunStatus, setLatestRunStatus] = useState("");
  const [scenarioRunResult, setScenarioRunResult] = useState<ApiAutomationScenarioRunResult | null>(null);
  const [runDrawerOpen, setRunDrawerOpen] = useState(false);
  const [aiPlan, setAiPlan] = useState<ApiScenarioAiReviewPlan | null>(null);
  const [activeAiPlanId, setActiveAiPlanId] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiLifecycleStatus, setAiLifecycleStatus] = useState<ApiScenarioAiPlanAccepted["lifecycle_status"] | null>(
    null,
  );
  const draftVersionRef = useRef(0);

  const applyScenario = useCallback((nextScenario: ApiAutomationScenario) => {
    draftVersionRef.current += 1;
    setScenario(nextScenario);
    setDraft({
      name: nextScenario.name,
      description: nextScenario.description,
      variables: nextScenario.variables,
      steps: nextScenario.steps,
    });
    setActiveStepId((current) =>
      current && nextScenario.steps.some((step) => step.id === current) ? current : (nextScenario.steps[0]?.id ?? ""),
    );
    setDirty(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError("");
      try {
        const [endpointRows, environmentRows, selectedScenario, revisionRows] = await Promise.all([
          listApiAutomationEndpoints(projectId),
          listApiAutomationEnvironments(projectId),
          scenarioId ? getApiAutomationScenario(projectId, scenarioId) : Promise.resolve(null),
          scenarioId ? listApiAutomationScenarioRevisions(projectId, scenarioId) : Promise.resolve([]),
        ]);
        if (cancelled) return;
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
        const persistedEnvironmentId = selectedScenario?.api_environment_id ?? "";
        setSelectedEnvironmentId(
          environmentRows.some((environment) => environment.id === initialEnvironmentId)
            ? initialEnvironmentId
            : environmentRows.some((environment) => environment.id === persistedEnvironmentId)
              ? persistedEnvironmentId
              : (environmentRows[0]?.id ?? ""),
        );
        setRevisions(revisionRows);
        if (selectedScenario) applyScenario(selectedScenario);
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "场景加载失败";
        setLoadError(message);
        toast.error(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [applyScenario, initialEnvironmentId, projectId, scenarioId]);

  useEffect(() => {
    if (!scenario?.id || aiPlan) return;
    const currentScenarioId = scenario.id;
    const storageKey = aiPlanStorageKey(projectId, currentScenarioId);
    const planId = activeAiPlanId || window.sessionStorage.getItem(storageKey);
    if (!planId) return;
    const recoveredPlanId = planId;
    let cancelled = false;
    let timer: number | undefined;
    async function recover() {
      try {
        const response = await getApiScenarioAiPlan(projectId, recoveredPlanId);
        if (cancelled) return;
        if (
          "schema_version" in response &&
          response.schema_version === 3 &&
          response.lifecycle_status === "completed"
        ) {
          setAiPlan(summarizeAiReviewPlan(response));
          setActiveAiPlanId("");
          setAiLifecycleStatus("completed");
          return;
        }
        if ("lifecycle_status" in response && response.lifecycle_status === "generating") {
          setAiLifecycleStatus("generating");
          timer = window.setTimeout(() => void recover(), 3000);
          return;
        }
        if ("lifecycle_status" in response && response.lifecycle_status === "failed") {
          setAiLifecycleStatus("failed");
          toast.error(("error" in response && response.error?.message) || "AI 编排失败");
        } else if ("lifecycle_status" in response && response.lifecycle_status === "expired") {
          setAiLifecycleStatus("expired");
          toast.error("AI 编排任务已过期，请重新提交");
        }
        window.sessionStorage.removeItem(storageKey);
        setActiveAiPlanId("");
      } catch {
        if (!cancelled) {
          window.sessionStorage.removeItem(storageKey);
          setActiveAiPlanId("");
        }
      }
    }
    void recover();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activeAiPlanId, aiPlan, projectId, scenario]);

  const refreshRevisions = useCallback(
    async (targetScenarioId: string) => {
      setRevisions(await listApiAutomationScenarioRevisions(projectId, targetScenarioId));
    },
    [projectId],
  );

  const activeStep = useMemo(
    () => draft.steps.find((step) => step.id === activeStepId) ?? draft.steps[0] ?? null,
    [activeStepId, draft.steps],
  );
  const selectedEnvironment = useMemo(
    () => environments.find((environment) => environment.id === selectedEnvironmentId) ?? null,
    [environments, selectedEnvironmentId],
  );
  const localValidation = useMemo(() => validateScenarioDraft(draft), [draft]);

  function markDraftChanged() {
    draftVersionRef.current += 1;
    setDirty(true);
  }

  function updateScenarioMeta(updates: Partial<Omit<ScenarioDraft, "steps">>) {
    setDraft((current) => ({ ...current, ...updates }));
    markDraftChanged();
  }

  function addEndpointSteps(endpointIds: string[]) {
    const selectedEndpoints = endpointIds
      .map((endpointId) => endpoints.find((endpoint) => endpoint.id === endpointId))
      .filter((endpoint): endpoint is ApiAutomationEndpoint => Boolean(endpoint));
    if (selectedEndpoints.length === 0) return;
    setDraft((current) => {
      const created = selectedEndpoints.map((endpoint, offset) => ({
        ...createEndpointStep(endpoint, projectId, scenario?.id ?? ""),
        step_order: current.steps.length + offset,
      }));
      setActiveStepId(created[0]?.id ?? "");
      return { ...current, steps: [...current.steps, ...created] };
    });
    markDraftChanged();
  }

  function addUtilityStep(stepType: Exclude<ApiAutomationScenarioStep["step_type"], "api_request">) {
    const step = createUtilityStep(stepType, projectId, scenario?.id ?? "");
    setDraft((current) => ({
      ...current,
      steps: [...current.steps, { ...step, step_order: current.steps.length }],
    }));
    setActiveStepId(step.id);
    markDraftChanged();
  }

  function updateStep(stepId: string, updates: Partial<ApiAutomationScenarioStep>) {
    setDraft((current) => ({
      ...current,
      steps: current.steps.map((step) => (step.id === stepId ? { ...step, ...updates } : step)),
    }));
    markDraftChanged();
  }

  function removeStep(stepId: string) {
    setDraft((current) => ({
      ...current,
      steps: current.steps
        .filter((step) => step.id !== stepId)
        .map((step, stepOrder) => ({ ...step, step_order: stepOrder })),
    }));
    setActiveStepId((current) => (current === stepId ? "" : current));
    markDraftChanged();
  }

  function reorderSteps(activeId: string, overId: string) {
    setDraft((current) => ({ ...current, steps: moveScenarioStep(current.steps, activeId, overId) }));
    markDraftChanged();
  }

  async function persistSelectedEnvironment(environmentId: string) {
    const previousEnvironmentId = selectedEnvironmentId;
    setSelectedEnvironmentId(environmentId);
    if (!scenario || environmentId === previousEnvironmentId) return;
    setEnvironmentSaving(true);
    try {
      const updated = await updateApiAutomationScenario(projectId, scenario.id, {
        name: scenario.name,
        description: scenario.description,
        variables: scenario.variables,
        api_environment_id: environmentId,
      });
      setScenario((current) =>
        current
          ? { ...current, api_environment_id: updated.api_environment_id, updated_at: updated.updated_at }
          : updated,
      );
      toast.success("运行环境已保存");
    } catch (error) {
      setSelectedEnvironmentId(previousEnvironmentId);
      toast.error(error instanceof Error ? error.message : "运行环境保存失败");
    } finally {
      setEnvironmentSaving(false);
    }
  }

  const saveScenario = useCallback(
    async (showToast = true) => {
      const draftVersion = draftVersionRef.current;
      const name = draft.name.trim();
      if (!name) throw new Error("请填写场景名称");
      const creating = !scenario;
      if (scenario && !dirty) {
        if (showToast) toast.success(`当前已是 v${scenario.revision}`);
        return scenario;
      }
      const target =
        scenario ??
        (await createApiAutomationScenario(projectId, {
          name,
          description: draft.description.trim(),
          variables: draft.variables,
          api_environment_id: selectedEnvironmentId || null,
        }));
      const saved = await saveApiAutomationScenarioVersion(projectId, target.id, {
        name,
        description: draft.description.trim(),
        variables: draft.variables,
        steps: draft.steps.map((step, stepOrder) => toScenarioStepInput(step, stepOrder)),
      });
      if (draftVersion === draftVersionRef.current) {
        applyScenario(saved);
      } else {
        setScenario((current) => current ?? saved);
      }
      if (creating) router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
      await refreshRevisions(saved.id);
      if (showToast) toast.success(`版本 v${saved.revision} 已保存`);
      return saved;
    },
    [applyScenario, dirty, draft, projectId, refreshRevisions, router, scenario, selectedEnvironmentId],
  );

  async function withBusy(action: () => Promise<void>) {
    setBusy(true);
    try {
      await action();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRestoreRevision(revision: number) {
    if (!scenario) return;
    if (!window.confirm(`确认以版本 v${revision} 的编排生成一个新版本？`)) return;
    await withBusy(async () => {
      const restored = await restoreApiAutomationScenarioRevision(projectId, scenario.id, revision);
      applyScenario(restored);
      await refreshRevisions(scenario.id);
      toast.success(`已从 v${revision} 生成版本 v${restored.revision}`);
    });
  }

  async function handleExecute() {
    if (!selectedEnvironmentId) {
      toast.error("请选择运行环境");
      return;
    }
    await withBusy(async () => {
      const saved = await saveScenario(false);
      const run = await executeApiAutomationScenario(projectId, saved.id, selectedEnvironmentId);
      setLatestRunId(run.id);
      setLatestRunStatus(run.status);
      setScenarioRunResult(null);
      setRunDrawerOpen(true);
      toast.success("场景运行已启动");
      await pollScenarioRun(run.id);
    });
  }

  async function generateAiPlan(goal: string, endpointIds: string[] = [], options: { requireCleanup?: boolean } = {}) {
    setAiBusy(true);
    setAiLifecycleStatus("generating");
    try {
      const name = draft.name.trim();
      if (!name) throw new Error("请填写场景名称");
      const creating = !scenario;
      const saved =
        scenario ??
        (await createApiAutomationScenario(projectId, {
          name,
          description: draft.description.trim(),
          variables: draft.variables,
          api_environment_id: selectedEnvironmentId || null,
        }));
      if (creating) {
        applyScenario(saved);
        router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
      }
      const accepted = await createApiScenarioAiPlan(projectId, {
        goal,
        scenario_id: saved.id,
        source_scope: { endpoint_ids: endpointIds },
        constraints: {
          environment_id: selectedEnvironmentId || null,
          require_cleanup: options.requireCleanup ?? false,
        },
      });
      window.sessionStorage.setItem(aiPlanStorageKey(projectId, saved.id), accepted.plan_id);
      setActiveAiPlanId(accepted.plan_id);
      notifyAiTaskStarted();
      toast.info("AI 编排任务已提交，可从顶部查看状态");
      return accepted;
    } catch (error) {
      setAiLifecycleStatus("failed");
      toast.error(error instanceof Error ? error.message : "AI 编排失败");
      return null;
    } finally {
      setAiBusy(false);
    }
  }

  function updateAiReviewField(
    stepId: string,
    fieldId: string,
    resolved: ApiScenarioAiPlanValueSource,
    status: "pending" | "confirmed" = "pending",
  ) {
    setAiPlan((current) => {
      if (!current) return current;
      return summarizeAiReviewPlan({
        ...current,
        steps: current.steps.map((step) =>
          step.step_id === stepId ? synchronizeReviewField(step, fieldId, resolved, status) : step,
        ),
      });
    });
  }

  function confirmAiReviewField(stepId: string, fieldId: string) {
    setAiPlan((current) => {
      if (!current) return current;
      return summarizeAiReviewPlan({
        ...current,
        steps: current.steps.map((step) =>
          step.step_id === stepId
            ? synchronizeReviewField(
                step,
                fieldId,
                step.field_groups.flatMap((group) => group.fields).find((field) => field.field_id === fieldId)
                  ?.resolved ??
                  step.field_groups.flatMap((group) => group.fields).find((field) => field.field_id === fieldId)
                    ?.proposal ?? { type: "literal", value: "" },
                "confirmed",
              )
            : step,
        ),
      });
    });
  }

  function confirmAiReviewStep(stepId: string) {
    setAiPlan((current) => {
      if (!current) return current;
      return summarizeAiReviewPlan({
        ...current,
        steps: current.steps.map((step) =>
          step.step_id === stepId
            ? {
                ...step,
                field_groups: step.field_groups.map((group) => ({
                  ...group,
                  fields: group.fields.map((field) => ({
                    ...field,
                    resolved: field.resolved ?? field.proposal,
                    status: "confirmed" as const,
                  })),
                })),
              }
            : step,
        ),
      });
    });
  }

  function confirmAllAiReviewFields() {
    setAiPlan((current) => {
      if (!current) return current;
      return summarizeAiReviewPlan({
        ...current,
        steps: current.steps.map((step) => ({
          ...step,
          field_groups: step.field_groups.map((group) => ({
            ...group,
            fields: group.fields.map((field) => ({
              ...field,
              resolved: field.resolved ?? field.proposal,
              status: "confirmed" as const,
            })),
          })),
        })),
      });
    });
  }

  function reorderAiReviewStep(stepId: string, direction: -1 | 1) {
    setAiPlan((current) => {
      if (!current) return current;
      const ordered = [...current.steps].sort((left, right) => left.order - right.order);
      const fromIndex = ordered.findIndex((step) => step.step_id === stepId);
      const toIndex = fromIndex + direction;
      if (fromIndex < 0 || toIndex < 0 || toIndex >= ordered.length) return current;
      [ordered[fromIndex], ordered[toIndex]] = [ordered[toIndex], ordered[fromIndex]];
      return summarizeAiReviewPlan({ ...current, steps: ordered });
    });
  }

  async function persistAiPlanReviewForApply(plan: ApiScenarioAiReviewPlan | null = aiPlan) {
    if (!plan) return null;
    const saved = await saveApiScenarioAiPlanReview(projectId, plan.plan_id, {
      expected_review_revision: plan.review_revision,
      steps: plan.steps.map((step) => ({
        step_id: step.step_id,
        order: step.order,
        fields: step.field_groups.flatMap((group) =>
          group.fields.map((field) => ({
            field_id: field.field_id,
            resolved: field.resolved ?? field.proposal,
            status: field.status === "pending" ? "pending" : "confirmed",
          })),
        ),
      })),
    });
    setAiPlan(saved);
    return saved;
  }

  async function applyAiPlan() {
    if (!aiPlan || !scenario) return false;
    setAiBusy(true);
    try {
      const savedPlan = await persistAiPlanReviewForApply();
      if (savedPlan?.review_status !== "ready") {
        toast.error("仍有字段待确认，请完成审核后再应用");
        return false;
      }
      const aiPlan = savedPlan;
      const applied = await applyApiScenarioAiPlan(projectId, aiPlan.plan_id, {
        expected_review_revision: aiPlan.review_revision,
        scenario_id: scenario.id,
        confirmation: "create_version",
      });
      applyScenario(applied);
      await refreshRevisions(scenario.id);
      setAiPlan(null);
      setAiLifecycleStatus(null);
      window.sessionStorage.removeItem(aiPlanStorageKey(projectId, scenario.id));
      toast.success(`AI 编排已生成版本 v${applied.revision}`);
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI 编排应用失败");
      return false;
    } finally {
      setAiBusy(false);
    }
  }

  async function pollScenarioRun(runId: string) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const run = await getApiAutomationRun(projectId, runId);
      setLatestRunStatus(run.status);
      if (["passed", "failed", "cancelled", "interrupted"].includes(run.status)) {
        if (run.target_type === "scenario" && run.scenario_result_path) {
          setScenarioRunResult(await getApiAutomationScenarioRunResult(projectId, runId));
        }
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, Math.min(1000 + attempt * 100, 3000)));
    }
    toast.error("运行仍在进行，请稍后从运行记录查看结果");
  }

  return {
    scenario,
    draft,
    endpoints,
    environments,
    selectedEnvironment,
    selectedEnvironmentId,
    activeStep,
    activeStepId,
    localValidation,
    latestRunId,
    latestRunStatus,
    scenarioRunResult,
    runDrawerOpen,
    aiPlan,
    aiBusy,
    aiLifecycleStatus,
    revisions,
    loading,
    loadError,
    busy,
    environmentSaving,
    dirty,
    actions: {
      persistSelectedEnvironment,
      setActiveStepId,
      setRunDrawerOpen,
      updateScenarioMeta,
      addEndpointSteps,
      addUtilityStep,
      updateStep,
      removeStep,
      reorderSteps,
      saveScenario: () => withBusy(async () => void (await saveScenario())),
      executeScenario: handleExecute,
      restoreRevision: handleRestoreRevision,
      generateAiPlan,
      updateAiReviewField,
      confirmAiReviewField,
      confirmAiReviewStep,
      confirmAllAiReviewFields,
      reorderAiReviewStep,
      applyAiPlan,
      discardAiPlan: () => {
        if (scenario?.id) window.sessionStorage.removeItem(aiPlanStorageKey(projectId, scenario.id));
        setActiveAiPlanId("");
        setAiPlan(null);
        setAiLifecycleStatus(null);
      },
    },
  };
}
