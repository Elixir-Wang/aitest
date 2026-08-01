"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioRevision,
  type ApiAutomationScenarioRunResult,
  type ApiAutomationScenarioStep,
  type ApiScenarioAiPlan,
  type ApiScenarioAiPlanAccepted,
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
  validateApiAutomationScenario,
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

function aiPlanStorageKey(projectId: string, scenarioId: string) {
  return `api-scenario-ai-plan:${projectId}:${scenarioId}`;
}

export function useApiScenarioEditor(projectId: string, scenarioId?: string) {
  const router = useRouter();
  const [scenario, setScenario] = useState<ApiAutomationScenario | null>(null);
  const [draft, setDraft] = useState<ScenarioDraft>(emptyDraft);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [activeStepId, setActiveStepId] = useState("");
  const [validation, setValidation] = useState<{ errors: string[]; warnings: string[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [latestRunId, setLatestRunId] = useState("");
  const [revisions, setRevisions] = useState<ApiAutomationScenarioRevision[]>([]);
  const [latestRunStatus, setLatestRunStatus] = useState("");
  const [scenarioRunResult, setScenarioRunResult] = useState<ApiAutomationScenarioRunResult | null>(null);
  const [runDrawerOpen, setRunDrawerOpen] = useState(false);
  const [aiPlan, setAiPlan] = useState<ApiScenarioAiPlan | null>(null);
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
        setSelectedEnvironmentId(environmentRows[0]?.id ?? "");
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
  }, [applyScenario, projectId, scenarioId]);

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
        if ("status" in response && response.status === "preview") {
          setAiPlan(response);
          setActiveAiPlanId("");
          setAiLifecycleStatus("completed");
          return;
        }
        if ("lifecycle_status" in response && response.lifecycle_status === "generating") {
          setAiLifecycleStatus("generating");
          timer = window.setTimeout(() => void recover(), 3000);
          return;
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
      setValidation(null);
      if (creating) router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
      await refreshRevisions(saved.id);
      if (showToast) toast.success(`版本 v${saved.revision} 已保存`);
      return saved;
    },
    [applyScenario, dirty, draft, projectId, refreshRevisions, router, scenario],
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

  async function handleSave() {
    await withBusy(async () => {
      await saveScenario(true);
    });
  }

  async function handleValidate() {
    await withBusy(async () => {
      const saved = await saveScenario(false);
      const result = await validateApiAutomationScenario(projectId, saved.id);
      setValidation({ errors: result.errors, warnings: result.warnings });
      toast[result.valid ? "success" : "error"](result.valid ? "场景检查通过" : `发现 ${result.errors.length} 个问题`);
    });
  }

  async function handleRestoreRevision(revision: number) {
    if (!scenario) return;
    if (!window.confirm(`确认以版本 v${revision} 的编排生成一个新版本？`)) return;
    await withBusy(async () => {
      const restored = await restoreApiAutomationScenarioRevision(projectId, scenario.id, revision);
      applyScenario(restored);
      await refreshRevisions(scenario.id);
      setValidation(null);
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
      const run = await executeApiAutomationScenario(projectId, saved.id, selectedEnvironmentId, "published");
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
      const saved = await saveScenario(false);
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

  async function applyAiPlan() {
    if (!aiPlan || !scenario) return;
    setAiBusy(true);
    try {
      const applied = await applyApiScenarioAiPlan(projectId, aiPlan.plan_id, {
        scenario_id: scenario.id,
        confirmation: "overwrite_draft",
      });
      applyScenario(applied);
      await refreshRevisions(scenario.id);
      setAiPlan(null);
      setAiLifecycleStatus(null);
      window.sessionStorage.removeItem(aiPlanStorageKey(projectId, scenario.id));
      setValidation(null);
      toast.success(`AI 编排已生成版本 v${applied.revision}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI 编排应用失败");
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
    validation,
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
    dirty,
    actions: {
      setSelectedEnvironmentId,
      setActiveStepId,
      setRunDrawerOpen,
      updateScenarioMeta,
      addEndpointSteps,
      addUtilityStep,
      updateStep,
      removeStep,
      reorderSteps,
      saveScenario: handleSave,
      validateScenario: handleValidate,
      executeScenario: handleExecute,
      restoreRevision: handleRestoreRevision,
      generateAiPlan,
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
