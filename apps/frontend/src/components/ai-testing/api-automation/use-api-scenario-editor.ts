"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { toast } from "@/lib/toast";

import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioRevision,
  type ApiAutomationScenarioRunResult,
  type ApiAutomationScenarioStep,
  ApiRequestError,
  type ApiScenarioAiPlan,
  applyApiScenarioAiPlan,
  createApiAutomationScenario,
  createApiScenarioAiPlan,
  executeApiAutomationScenario,
  getApiAutomationRun,
  getApiScenarioAiPlan,
  getApiAutomationScenario,
  getApiAutomationScenarioRunResult,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  listApiAutomationScenarioRevisions,
  publishApiAutomationScenario,
  replaceApiAutomationScenarioSteps,
  restoreApiAutomationScenarioRevision,
  updateApiAutomationScenario,
  validateApiAutomationScenario,
} from "@/lib/api-client";

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
  const [aiBusy, setAiBusy] = useState(false);
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
    const storageKey = aiPlanStorageKey(projectId, scenario.id);
    const planId = window.sessionStorage.getItem(storageKey);
    if (!planId) return;
    let cancelled = false;
    void getApiScenarioAiPlan(projectId, planId)
      .then((plan) => {
        if (cancelled) return;
        if (plan.status === "preview") setAiPlan(plan);
        else window.sessionStorage.removeItem(storageKey);
      })
      .catch(() => {
        if (!cancelled) window.sessionStorage.removeItem(storageKey);
      });
    return () => {
      cancelled = true;
    };
  }, [aiPlan, projectId, scenario?.id]);

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
      const target = scenario
        ? await updateApiAutomationScenario(projectId, scenario.id, {
            name,
            description: draft.description.trim(),
            variables: draft.variables,
          })
        : await createApiAutomationScenario(projectId, {
            name,
            description: draft.description.trim(),
            variables: draft.variables,
          });
      const saved = await replaceApiAutomationScenarioSteps(
        projectId,
        target.id,
        draft.steps.map((step, stepOrder) => toScenarioStepInput(step, stepOrder)),
      );
      if (draftVersion === draftVersionRef.current) {
        applyScenario(saved);
      } else {
        setScenario((current) => current ?? saved);
      }
      setValidation(null);
      if (creating) router.replace(`/projects/${projectId}/automation/api/scenarios/${saved.id}`);
      if (showToast) toast.success(creating ? "场景已创建" : "场景已保存");
      return saved;
    },
    [applyScenario, draft, projectId, router, scenario],
  );

  useEffect(() => {
    if (!scenario || !dirty || busy || !localValidation.valid) return;
    const timer = window.setTimeout(() => {
      void saveScenario(false).catch(() => undefined);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [busy, dirty, localValidation.valid, saveScenario, scenario]);

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

  async function handlePublish() {
    if (!scenario) return;
    await withBusy(async () => {
      const saved = await saveScenario(false);
      try {
        applyScenario(await publishApiAutomationScenario(projectId, saved.id));
      } catch (error) {
        if (!(error instanceof ApiRequestError) || error.code !== "API_SCENARIO_ASSET_CHANGES_UNCONFIRMED") throw error;
        const changes = saved.asset_changes
          .map(
            (change) =>
              `${saved.steps.find((step) => step.id === change.step_id)?.name ?? change.endpoint_id}: ${change.fields.join("、")}`,
          )
          .join("\n");
        if (!window.confirm(`接口资产已发生变化：\n${changes}\n\n确认使用最新资产发布？`)) return;
        applyScenario(await publishApiAutomationScenario(projectId, saved.id, true));
      }
      await refreshRevisions(saved.id);
      toast.success("场景已发布");
    });
  }

  async function handleRestoreRevision(revision: number) {
    if (!scenario) return;
    if (!window.confirm(`确认将版本 v${revision} 恢复为当前草稿？当前未发布修改会被覆盖。`)) return;
    await withBusy(async () => {
      applyScenario(await restoreApiAutomationScenarioRevision(projectId, scenario.id, revision));
      await refreshRevisions(scenario.id);
      setValidation(null);
      toast.success(`已将版本 v${revision} 恢复为草稿`);
    });
  }

  async function handleExecute(source: "published" | "draft" = "published") {
    if (!selectedEnvironmentId) {
      toast.error("请选择运行环境");
      return;
    }
    await withBusy(async () => {
      const saved = await saveScenario(false);
      const run = await executeApiAutomationScenario(projectId, saved.id, selectedEnvironmentId, source);
      setLatestRunId(run.id);
      setLatestRunStatus(run.status);
      setScenarioRunResult(null);
      setRunDrawerOpen(true);
      toast.success(source === "draft" ? "草稿运行已启动" : "场景运行已启动");
      await pollScenarioRun(run.id);
    });
  }

  async function generateAiPlan(goal: string, allowWrite: boolean, maxSteps: number) {
    setAiBusy(true);
    try {
      const saved = await saveScenario(false);
      const plan = await createApiScenarioAiPlan(projectId, {
        goal,
        scenario_id: saved.id,
        constraints: {
          environment_id: selectedEnvironmentId || null,
          max_steps: maxSteps,
          allow_write: allowWrite,
          require_cleanup: false,
        },
      });
      setAiPlan(plan);
      window.sessionStorage.setItem(aiPlanStorageKey(projectId, saved.id), plan.plan_id);
      return plan;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI 编排失败");
      return null;
    } finally {
      setAiBusy(false);
    }
  }

  async function applyAiPlan() {
    if (!aiPlan || !scenario || aiPlan.expected_revision === null) return;
    setAiBusy(true);
    try {
      const applied = await applyApiScenarioAiPlan(projectId, aiPlan.plan_id, {
        scenario_id: scenario.id,
        expected_revision: aiPlan.expected_revision,
        confirmation: "apply_preview",
      });
      applyScenario(applied);
      setAiPlan(null);
      window.sessionStorage.removeItem(aiPlanStorageKey(projectId, scenario.id));
      setValidation(null);
      toast.success("AI 编排已应用到场景草稿");
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
      publishScenario: handlePublish,
      executeScenario: handleExecute,
      restoreRevision: handleRestoreRevision,
      generateAiPlan,
      applyAiPlan,
      discardAiPlan: () => {
        if (scenario?.id) window.sessionStorage.removeItem(aiPlanStorageKey(projectId, scenario.id));
        setAiPlan(null);
      },
    },
  };
}
