"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { ArrowLeft, CircleHelp, FileText, Gauge, Loader2, Play, Save, Sparkles } from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Loader } from "@/components/ui/loader";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import type {
  ExplorationEnvironment,
  ExplorationMode,
  ExplorationRunSummary as ExplorationRun,
  ExplorationRunDetail,
  ProjectScope,
} from "@/lib/exploration-types";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

type RequirementDocument = {
  id: string;
  name: string;
  status: string;
  current_version_id: string | null;
};

type ExplorationGoalOptimizeResult = {
  optimized_goal: string;
};

type ExplorationForm = {
  title: string;
  projectId: string;
  environmentId: string;
  requirementDocId: string;
  explorationMode: ExplorationMode;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};

type ExplorationRunCreatePageProps = {
  mode?: "create" | "edit";
  projectId?: string;
  projectName?: string;
  projectScope: ProjectScope;
  runId?: string;
};

const NO_REQUIREMENT_VALUE = "__none__";
const EXPLORATION_GOAL_MAX_LENGTH = 4000;

const emptyExplorationForm: ExplorationForm = {
  title: "",
  projectId: "",
  environmentId: "",
  requirementDocId: "",
  explorationMode: "goal",
  scope: "",
  forbiddenPaths: "",
  goal: "",
  notes: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};

const explorationPlaceholders = {
  scope: "填写本次探索要覆盖的页面、模块或 URL 范围。",
  forbiddenPaths: "填写本次探索需要避开的路径、页面或操作。",
  goal: "填写本次探索想发现或验证的目标。",
  autonomousGoal: "可选填写本次自主探索想重点关注的内容。",
  loopGoal: "可选填写 Loop 探索的重点模块或业务风险。",
};

const explorationModeLabels: Record<ExplorationMode, string> = {
  goal: "目标探索",
  autonomous: "自主探索",
  loop: "Loop 全站探索",
};

function isExplorationLinkableRequirement(requirement: RequirementDocument) {
  return Boolean(requirement.current_version_id);
}

function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function resizeTextarea(textarea: HTMLTextAreaElement | null) {
  if (!textarea) {
    return;
  }
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

export function ExplorationRunCreatePage({
  mode = "create",
  projectId,
  projectName = "",
  projectScope,
  runId,
}: ExplorationRunCreatePageProps) {
  const router = useRouter();
  const isEditing = mode === "edit";
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [environments, setEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [requirements, setRequirements] = useState<RequirementDocument[]>([]);
  const [projectLoading, setProjectLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(true);
  const [requirementLoading, setRequirementLoading] = useState(false);
  const [runLoading, setRunLoading] = useState(isEditing);
  const [loadedRunTitle, setLoadedRunTitle] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [goalOptimizeLoading, setGoalOptimizeLoading] = useState(false);
  const scopeRef = useRef<HTMLTextAreaElement | null>(null);
  const forbiddenPathsRef = useRef<HTMLTextAreaElement | null>(null);
  const goalRef = useRef<HTMLTextAreaElement | null>(null);
  const notesRef = useRef<HTMLTextAreaElement | null>(null);
  const [form, setForm] = useState<ExplorationForm>({
    ...emptyExplorationForm,
    projectId: projectId ?? "",
  });
  const selectedProjectId = projectScope === "project" ? (projectId ?? "") : form.projectId;

  useEffect(() => {
    resizeTextarea(scopeRef.current);
    resizeTextarea(forbiddenPathsRef.current);
    resizeTextarea(goalRef.current);
    resizeTextarea(notesRef.current);
  });

  useEffect(() => {
    setForm((current) => ({ ...current, projectId: projectId ?? current.projectId }));
  }, [projectId]);

  useEffect(() => {
    let ignore = false;
    if (!isEditing || !runId) {
      setRunLoading(false);
      return;
    }

    async function loadExplorationRun() {
      setRunLoading(true);
      try {
        const detail = await apiRequest<ExplorationRunDetail>(`/page-exploration/runs/${runId}`);
        if (ignore) {
          return;
        }
        const run = detail.run;
        setLoadedRunTitle(run.title);
        setForm({
          title: run.title,
          projectId: run.project_id,
          environmentId: run.environment_id,
          requirementDocId: run.requirement_doc_id ?? "",
          explorationMode: run.exploration_mode ?? "goal",
          scope: run.scope ?? "",
          forbiddenPaths: run.forbidden_paths ?? "",
          goal: run.goal ?? "",
          notes: run.notes ?? "",
          maxPages: String(run.max_pages ?? 50),
          maxActions: String(run.max_actions ?? 1000),
          timeoutMinutes: String(run.timeout_minutes ?? 120),
        });
      } catch (requestError) {
        if (!ignore) {
          reportError(requestError, {
            fallbackMessage: "探索任务加载失败",
            actionLabel: "加载探索任务",
            method: "GET",
            path: `/page-exploration/runs/${runId}`,
          });
        }
      } finally {
        if (!ignore) {
          setRunLoading(false);
        }
      }
    }

    void loadExplorationRun();

    return () => {
      ignore = true;
    };
  }, [isEditing, runId]);

  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      setProjectLoading(true);
      try {
        const data = await apiRequest<ApiProject[]>("/projects");
        if (ignore) {
          return;
        }
        setProjects(data);
        if (!projectId) {
          const firstActiveProject = data.find((item) => item.status !== "archived");
          setForm((current) => ({ ...current, projectId: current.projectId || firstActiveProject?.id || "" }));
        }
      } catch (requestError) {
        if (!ignore) {
          reportError(requestError, {
            fallbackMessage: "项目列表加载失败",
            actionLabel: "加载项目",
            method: "GET",
            path: "/projects",
          });
        }
      } finally {
        if (!ignore) {
          setProjectLoading(false);
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, [projectId]);

  useEffect(() => {
    let ignore = false;

    async function loadEnvironments() {
      if (!selectedProjectId) {
        setEnvironments([]);
        setEnvironmentLoading(false);
        setForm((current) => ({ ...current, environmentId: "" }));
        return;
      }
      setEnvironmentLoading(true);
      try {
        const path = `/environments?project_id=${selectedProjectId}`;
        const data = await apiRequest<ExplorationEnvironment[]>(path);
        if (!ignore) {
          setEnvironments(data);
          setForm((current) => ({
            ...current,
            environmentId: data.some((environment) => environment.id === current.environmentId)
              ? current.environmentId
              : "",
          }));
        }
      } catch (requestError) {
        if (!ignore) {
          reportError(requestError, {
            fallbackMessage: "环境列表加载失败",
            actionLabel: "加载环境",
            method: "GET",
            path: `/environments?project_id=${selectedProjectId}`,
          });
        }
      } finally {
        if (!ignore) {
          setEnvironmentLoading(false);
        }
      }
    }

    void loadEnvironments();

    return () => {
      ignore = true;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    let ignore = false;
    if (!selectedProjectId) {
      setRequirements([]);
      setRequirementLoading(false);
      return;
    }

    async function loadRequirements() {
      setRequirementLoading(true);
      try {
        const data = await apiRequest<RequirementDocument[]>(`/projects/${selectedProjectId}/requirements`);
        if (!ignore) {
          setRequirements(data);
          setForm((current) => ({
            ...current,
            requirementDocId: data.some((item) =>
              isEditing
                ? item.id === current.requirementDocId
                : item.id === current.requirementDocId && isExplorationLinkableRequirement(item),
            )
              ? current.requirementDocId
              : "",
          }));
        }
      } catch (requestError) {
        if (!ignore) {
          setRequirements([]);
          reportError(requestError, {
            fallbackMessage: "需求列表加载失败",
            actionLabel: "加载需求",
            method: "GET",
            path: `/projects/${selectedProjectId}/requirements`,
          });
        }
      } finally {
        if (!ignore) {
          setRequirementLoading(false);
        }
      }
    }

    void loadRequirements();

    return () => {
      ignore = true;
    };
  }, [selectedProjectId, isEditing]);

  const scopedProjectName =
    (projectName.trim() ? projectName : undefined) ??
    projects.find((project) => project.id === projectId)?.name ??
    projectId ??
    "";
  const activeProjects = projects.filter((project) => project.status !== "archived");
  const availableRequirements = useMemo(() => {
    const linkable = requirements.filter(
      (requirement) => requirement.status !== "archived" && isExplorationLinkableRequirement(requirement),
    );
    if (!isEditing || !form.requirementDocId) {
      return linkable;
    }
    const linkedRequirement = requirements.find((requirement) => requirement.id === form.requirementDocId);
    if (!linkedRequirement || linkable.some((requirement) => requirement.id === form.requirementDocId)) {
      return linkable;
    }
    return [linkedRequirement, ...linkable];
  }, [form.requirementDocId, isEditing, requirements]);
  const maxPages = parsePositiveInteger(form.maxPages);
  const maxActions = parsePositiveInteger(form.maxActions);
  const timeoutMinutes = parsePositiveInteger(form.timeoutMinutes);
  const canCreate =
    selectedProjectId.length > 0 &&
    form.title.trim().length > 0 &&
    form.environmentId.length > 0 &&
    Boolean(maxPages && maxActions && timeoutMinutes);
  const canSubmit = canCreate && !runLoading;
  const backHref =
    isEditing && runId
      ? `/projects/${selectedProjectId || projectId}/exploration/${runId}`
      : projectId
        ? `/projects/${projectId}`
        : "/exploration";
  const pageBreadcrumbs =
    isEditing && runId
      ? moduleBreadcrumbs(
          "exploration",
          ...(loadedRunTitle
            ? [
                {
                  label: loadedRunTitle,
                  href: `/projects/${projectId ?? selectedProjectId}/exploration/${runId}`,
                },
              ]
            : []),
          { label: "编辑探索任务" },
        )
      : moduleBreadcrumbs("exploration", { label: "新建探索任务" });

  const requestGoalOptimization = useCallback(async () => {
    if (!selectedProjectId) {
      toast.error("请选择项目");
      return;
    }
    const normalizedGoal = form.goal.trim();
    if (!normalizedGoal) {
      toast.error(form.explorationMode === "autonomous" ? "请先输入补充关注点" : "请先输入探索目标");
      return;
    }
    if (normalizedGoal.length > EXPLORATION_GOAL_MAX_LENGTH) {
      toast.error(`探索目标不能超过 ${EXPLORATION_GOAL_MAX_LENGTH} 字`);
      return;
    }

    setGoalOptimizeLoading(true);
    try {
      const result = await apiRequest<ExplorationGoalOptimizeResult>(
        `/projects/${selectedProjectId}/exploration-goal/optimize`,
        {
          method: "POST",
          body: JSON.stringify({ goal: normalizedGoal }),
        },
      );
      setForm((current) => ({ ...current, goal: result.optimized_goal }));
      toast.success("探索目标已优化");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索目标优化失败",
        actionLabel: "优化探索目标",
        method: "POST",
        path: `/projects/${selectedProjectId}/exploration-goal/optimize`,
      });
    } finally {
      setGoalOptimizeLoading(false);
    }
  }, [form.explorationMode, form.goal, selectedProjectId]);

  async function saveExplorationRun() {
    if (!canSubmit || !maxPages || !maxActions || !timeoutMinutes) {
      toast.error("请填写任务名称、项目、环境和大于 0 的执行边界");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        environment_id: form.environmentId,
        requirement_doc_id: form.requirementDocId,
        exploration_mode: form.explorationMode,
        title: form.title,
        scope: form.scope,
        forbidden_paths: form.forbiddenPaths,
        goal: form.goal,
        notes: form.notes,
        max_pages: maxPages,
        max_actions: maxActions,
        timeout_minutes: timeoutMinutes,
      };

      if (isEditing && runId) {
        const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${runId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast.success("探索任务已更新");
        router.push(`/projects/${updated.project_id}/exploration/${updated.id}`);
        return;
      }

      const created = await apiRequest<ExplorationRun>("/page-exploration/runs", {
        method: "POST",
        body: JSON.stringify({
          project_id: selectedProjectId,
          ...payload,
        }),
      });
      toast.success("探索任务已创建");
      notifyAiTaskStarted();
      router.push(`/projects/${created.project_id}/exploration/${created.id}`);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: isEditing ? "探索任务更新失败" : "探索任务创建失败",
        actionLabel: isEditing ? "更新探索任务" : "创建探索任务",
        method: isEditing ? "PATCH" : "POST",
        path: isEditing && runId ? `/page-exploration/runs/${runId}` : "/page-exploration/runs",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={pageBreadcrumbs}
      description={
        isEditing
          ? "调整页面探索任务的目标、范围、环境和执行边界。"
          : "配置目标、范围、环境和执行边界后创建页面探索任务。"
      }
      projectScope={projectScope}
      title={isEditing ? "编辑探索任务" : "新建探索任务"}
    >
      <div className="w-full">
        <ShellSection className="overflow-hidden p-0">
          {runLoading ? (
            <div className="flex min-h-64 items-center justify-center text-muted-foreground text-sm">
              <Loader className="mr-2" size={16} />
              探索任务加载中
            </div>
          ) : (
            <FieldGroup className="grid gap-x-5 gap-y-4 p-5 md:grid-cols-2">
              <div className="flex items-center justify-between gap-2 border-b pb-2 md:col-span-2">
                <div className="flex items-center gap-2">
                  <FileText className="size-4 text-muted-foreground" />
                  <h3 className="font-semibold text-base">基础信息</h3>
                </div>
                <div className="flex items-center gap-2">
                  <Button onClick={() => router.push(backHref)} variant="outline">
                    <ArrowLeft className="size-4" />
                    返回
                  </Button>
                  <Button disabled={!canSubmit || submitting} onClick={saveExplorationRun} type="button">
                    {submitting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : isEditing ? (
                      <Save className="size-4" />
                    ) : (
                      <Play className="size-4" />
                    )}
                    {isEditing ? "保存" : "创建任务"}
                  </Button>
                </div>
              </div>
              <Field>
                <FieldLabel htmlFor="exploration-title">任务名称 *</FieldLabel>
                <Input
                  aria-required="true"
                  id="exploration-title"
                  onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="后台管理系统核心流程探索"
                  value={form.title}
                />
              </Field>
              <Field>
                <div className="flex items-center gap-1.5">
                  <FieldLabel htmlFor="exploration-mode">探索方式</FieldLabel>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          aria-label="探索方式说明"
                          className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
                          type="button"
                        >
                          <CircleHelp className="size-3.5" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-80" side="top">
                        <div className="space-y-1 text-xs">
                          <p>
                            <span className="font-medium">目标探索：</span>
                            围绕明确目标验证页面流程、异常跳转和关键状态。
                          </p>
                          <p>
                            <span className="font-medium">自主探索：</span>
                            自动盘点指定范围内的主要页面、功能入口和交互元素。
                          </p>
                          <p>
                            <span className="font-medium">Loop 全站探索：</span>
                            以页面状态和待探索队列持续推进，动作后验证并合并项目探索产物。
                          </p>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <Select
                  id="exploration-mode"
                  placeholder="选择探索方式"
                  setValue={(value) =>
                    setForm((current) => ({ ...current, explorationMode: value as ExplorationMode }))
                  }
                  value={form.explorationMode}
                >
                  {(["goal", "autonomous", "loop"] as const).map((mode) => (
                    <SelectOption key={mode} value={mode}>
                      {explorationModeLabels[mode]}
                    </SelectOption>
                  ))}
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="exploration-project">项目 *</FieldLabel>
                <Select
                  disabled={isEditing || projectScope === "project" || projectLoading}
                  id="exploration-project"
                  placeholder={projectScope === "project" ? scopedProjectName : "选择项目"}
                  setValue={(value) =>
                    setForm((current) => ({
                      ...current,
                      projectId: value,
                      requirementDocId: "",
                    }))
                  }
                  value={selectedProjectId}
                >
                  {projectScope === "project" && projectId ? (
                    <SelectOption value={projectId}>{scopedProjectName}</SelectOption>
                  ) : (
                    activeProjects.map((project) => (
                      <SelectOption key={project.id} value={project.id}>
                        {project.name}
                      </SelectOption>
                    ))
                  )}
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="exploration-environment">环境 *</FieldLabel>
                <Select
                  disabled={environmentLoading || !selectedProjectId}
                  id="exploration-environment"
                  placeholder={!selectedProjectId ? "请先选择项目" : environmentLoading ? "加载环境中..." : "选择环境"}
                  setValue={(value) => setForm((current) => ({ ...current, environmentId: value }))}
                  value={form.environmentId}
                >
                  {environments.map((environment) => (
                    <SelectOption key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectOption>
                  ))}
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="exploration-requirement">需求</FieldLabel>
                <Select
                  disabled={requirementLoading || !selectedProjectId}
                  id="exploration-requirement"
                  placeholder={requirementLoading ? "加载需求中..." : "选择需求或留空"}
                  setValue={(value) =>
                    setForm((current) => ({
                      ...current,
                      requirementDocId: value === NO_REQUIREMENT_VALUE ? "" : value,
                    }))
                  }
                  value={form.requirementDocId || NO_REQUIREMENT_VALUE}
                >
                  <SelectOption value={NO_REQUIREMENT_VALUE}>不关联需求</SelectOption>
                  {availableRequirements.map((requirement) => (
                    <SelectOption key={requirement.id} value={requirement.id}>
                      {requirement.name}
                    </SelectOption>
                  ))}
                </Select>
                {!requirementLoading && selectedProjectId && availableRequirements.length === 0 ? (
                  <p className="text-muted-foreground text-xs">当前项目没有可关联的需求，可直接创建探索任务。</p>
                ) : null}
              </Field>
              <Field className="md:col-span-2">
                <div className="mt-1 flex items-center gap-2 border-b pb-2">
                  <Gauge className="size-4 text-muted-foreground" />
                  <h3 className="font-semibold text-base">探索边界</h3>
                </div>
              </Field>
              <Field>
                <FieldLabel htmlFor="exploration-scope">探索范围</FieldLabel>
                <Textarea
                  className="min-h-[3.75rem] resize-none overflow-hidden"
                  id="exploration-scope"
                  onChange={(event) => setForm((current) => ({ ...current, scope: event.target.value }))}
                  onInput={(event) => resizeTextarea(event.currentTarget)}
                  placeholder={explorationPlaceholders.scope}
                  ref={scopeRef}
                  rows={2}
                  value={form.scope}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="exploration-forbidden-paths">禁止路径</FieldLabel>
                <Textarea
                  className="min-h-[3.75rem] resize-none overflow-hidden"
                  id="exploration-forbidden-paths"
                  onChange={(event) => setForm((current) => ({ ...current, forbiddenPaths: event.target.value }))}
                  onInput={(event) => resizeTextarea(event.currentTarget)}
                  placeholder={explorationPlaceholders.forbiddenPaths}
                  ref={forbiddenPathsRef}
                  rows={2}
                  value={form.forbiddenPaths}
                />
              </Field>
              <Field className="md:col-span-2">
                <div className="flex items-center justify-between gap-3">
                  <FieldLabel htmlFor="exploration-goal">
                    {form.explorationMode === "autonomous" || form.explorationMode === "loop"
                      ? "补充关注点"
                      : "探索目标"}
                  </FieldLabel>
                  <Button
                    className="border-primary/20 bg-primary/10 text-primary hover:bg-primary/15 hover:text-primary"
                    disabled={goalOptimizeLoading}
                    onClick={requestGoalOptimization}
                    size="sm"
                    type="button"
                    variant="outline"
                  >
                    {goalOptimizeLoading ? <Loader size={14} /> : <Sparkles className="size-4" />}
                    AI 生成
                  </Button>
                </div>
                <Textarea
                  className="min-h-[3.75rem] resize-none overflow-hidden"
                  id="exploration-goal"
                  maxLength={EXPLORATION_GOAL_MAX_LENGTH}
                  onChange={(event) => setForm((current) => ({ ...current, goal: event.target.value }))}
                  onInput={(event) => resizeTextarea(event.currentTarget)}
                  placeholder={
                    form.explorationMode === "autonomous"
                      ? explorationPlaceholders.autonomousGoal
                      : form.explorationMode === "loop"
                        ? explorationPlaceholders.loopGoal
                        : explorationPlaceholders.goal
                  }
                  ref={goalRef}
                  rows={2}
                  value={form.goal}
                />
              </Field>
              <Field className="md:col-span-2">
                <FieldLabel htmlFor="exploration-notes">备注</FieldLabel>
                <Textarea
                  className="min-h-[3.75rem] resize-none overflow-hidden"
                  id="exploration-notes"
                  onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                  onInput={(event) => resizeTextarea(event.currentTarget)}
                  placeholder="补充说明，不参与探索目标判定"
                  ref={notesRef}
                  rows={2}
                  value={form.notes}
                />
              </Field>
              <Field className="md:col-span-2">
                <FieldLabel>执行边界 *</FieldLabel>
                <div className="grid gap-3 sm:grid-cols-3">
                  <label className="grid gap-1.5 text-sm" htmlFor="exploration-max-pages">
                    <span className="text-muted-foreground text-xs">页面上限</span>
                    <Input
                      id="exploration-max-pages"
                      inputMode="numeric"
                      min={1}
                      onChange={(event) => setForm((current) => ({ ...current, maxPages: event.target.value }))}
                      placeholder="50"
                      type="number"
                      value={form.maxPages}
                    />
                  </label>
                  <label className="grid gap-1.5 text-sm" htmlFor="exploration-max-actions">
                    <span className="text-muted-foreground text-xs">操作上限</span>
                    <Input
                      id="exploration-max-actions"
                      inputMode="numeric"
                      min={1}
                      onChange={(event) => setForm((current) => ({ ...current, maxActions: event.target.value }))}
                      placeholder="1000"
                      type="number"
                      value={form.maxActions}
                    />
                  </label>
                  <label className="grid gap-1.5 text-sm" htmlFor="exploration-timeout-minutes">
                    <span className="text-muted-foreground text-xs">超时时间（分钟）</span>
                    <Input
                      id="exploration-timeout-minutes"
                      inputMode="numeric"
                      min={1}
                      onChange={(event) => setForm((current) => ({ ...current, timeoutMinutes: event.target.value }))}
                      placeholder="120"
                      type="number"
                      value={form.timeoutMinutes}
                    />
                  </label>
                </div>
              </Field>
            </FieldGroup>
          )}
        </ShellSection>
      </div>
    </PageShell>
  );
}
