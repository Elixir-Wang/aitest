"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import Link from "next/link";

import { ClipboardCheck, Loader2, Plus, RefreshCw, Sparkles, Trash2 } from "lucide-react";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiManualTestCase,
  type ApiManualTestCaseAiGenerateRequest,
  type ApiManualTestCaseAiGenerateResult,
  type ApiManualTestCaseCreate,
  type ApiProject,
  type ApiRequirementDocument,
  type ApiTestCaseGenerationScopeType,
  type ApiTestCaseSet,
  type ApiTestCaseSetCreate,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

type TestCaseSetForm = {
  name: string;
  projectId: string;
  requirementDocId: string;
  generationScopeType: ApiTestCaseGenerationScopeType;
  generationScopeText: string;
  notes: string;
};

type CreateMode = "case" | "set";

type ManualTestCaseForm = {
  title: string;
  projectId: string;
  preconditions: string;
  steps: Array<{ id: string; action: string; expected_result: string }>;
  notes: string;
};

type TestCaseListItem = (ApiTestCaseSet & { itemType: "set" }) | (ApiManualTestCase & { itemType: "case" });

const NO_EXPLORATION_ARTIFACTS_VALUE = "no_exploration_artifacts";
const NO_COMPANY_KNOWLEDGE_VALUE = "no_company_knowledge";
const ACTIVE_GENERATION_STATUSES = new Set(["queued", "running"]);
const TEST_CASE_SET_POLL_INTERVAL_MS = 5000;
const finalRequirementVersionActions = new Set(["requirement_analysis", "requirement_analysis_finalize"]);
const testCaseSetStatusLabels: Record<string, string> = {
  generating: "生成中",
  ready_for_review: "待评审",
  review_completed: "评审完成",
  failed: "生成失败",
  archived: "已归档",
};

function isFinalRequirement(requirement: ApiRequirementDocument) {
  return requirement.current_version
    ? finalRequirementVersionActions.has(requirement.current_version.source_action)
    : false;
}

function isTestCaseSetGenerating(item: ApiTestCaseSet) {
  return item.generation_run
    ? ACTIVE_GENERATION_STATUSES.has(item.generation_run.status)
    : item.status === "generating";
}

function testCaseSetStatusLabel(item: ApiTestCaseSet) {
  return testCaseSetStatusLabels[item.status] ?? item.status_label;
}

const emptyForm: TestCaseSetForm = {
  name: "",
  projectId: "",
  requirementDocId: "",
  generationScopeType: "all",
  generationScopeText: "",
  notes: "",
};

const emptyManualForm: ManualTestCaseForm = {
  title: "",
  projectId: "",
  preconditions: "",
  steps: [{ id: "step-1", action: "", expected_result: "" }],
  notes: "",
};

function manualFormHasContent(form: ManualTestCaseForm) {
  return Boolean(
    form.title.trim() ||
      form.preconditions.trim() ||
      form.steps.some((step) => step.action.trim() || step.expected_result.trim()),
  );
}

export default function Page() {
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const itemSelection = useLocalTableSelection<TestCaseListItem>([]);
  const [requirements, setRequirements] = useState<ApiRequirementDocument[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>("case");
  const [form, setForm] = useState<TestCaseSetForm>({ ...emptyForm });
  const [manualForm, setManualForm] = useState<ManualTestCaseForm>({ ...emptyManualForm });
  const manualFormRef = useRef(manualForm);
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [aiDescription, setAiDescription] = useState("");
  const [includeExplorationArtifacts, setIncludeExplorationArtifacts] = useState(true);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [pendingAiResult, setPendingAiResult] = useState<ApiManualTestCaseAiGenerateResult | null>(null);
  const [overwriteDialogOpen, setOverwriteDialogOpen] = useState(false);

  useEffect(() => {
    if (!hasHydrated) {
      hydrate();
    }
  }, [hasHydrated, hydrate]);

  useEffect(() => {
    manualFormRef.current = manualForm;
  }, [manualForm]);

  const selectedProjectId = projectScope === "project" ? (currentProjectId ?? "") : form.projectId;
  const selectedManualProjectId = projectScope === "project" ? (currentProjectId ?? "") : manualForm.projectId;
  const currentProjectName =
    projectScope === "project" ? (projects.find((item) => item.id === currentProjectId)?.name ?? "") : "";
  const selectedProjectName =
    projectScope === "project" ? currentProjectName : (projects.find((item) => item.id === form.projectId)?.name ?? "");
  const finalRequirements = requirements.filter(isFinalRequirement);

  const filteredRows = itemSelection.rows.filter((item) => {
    const searchableValues =
      item.itemType === "case"
        ? [item.title, item.project_name, item.preconditions, item.notes]
        : [item.name, testCaseSetStatusLabel(item)];
    return searchableValues.some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase()));
  });

  const loadProjects = useCallback(async () => {
    const data = await apiRequest<ApiProject[]>("/projects");
    setProjects(data);
  }, []);

  const loadProjectInputs = useCallback(async (nextProjectId: string) => {
    if (!nextProjectId) {
      setRequirements([]);
      return;
    }
    const nextRequirements = await apiRequest<ApiRequirementDocument[]>(`/projects/${nextProjectId}/requirements`);
    setRequirements(nextRequirements);
  }, []);

  const loadItems = useCallback(
    async (nextProjectIds: string[], options?: { silent?: boolean }) => {
      if (nextProjectIds.length === 0) {
        itemSelection.setRows([]);
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      try {
        const data = await Promise.all(
          nextProjectIds.map(async (projectId) => {
            const [sets, manualCases] = await Promise.all([
              apiRequest<ApiTestCaseSet[]>(`/projects/${projectId}/test-case-sets`),
              apiRequest<ApiManualTestCase[]>(`/projects/${projectId}/test-cases`),
            ]);
            return [
              ...manualCases.map((item): TestCaseListItem => ({ ...item, itemType: "case" })),
              ...sets.map((item): TestCaseListItem => ({ ...item, itemType: "set" })),
            ];
          }),
        );
        itemSelection.setRows(data.flat().sort((first, second) => second.updated_at.localeCompare(first.updated_at)));
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [itemSelection.setRows],
  );

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    const nextProjectId = projectScope === "project" ? (currentProjectId ?? "") : (projects[0]?.id ?? "");
    setForm((current) => ({
      ...current,
      projectId: nextProjectId,
      requirementDocId: current.projectId === nextProjectId ? current.requirementDocId : "",
    }));
    setManualForm((current) => ({ ...current, projectId: nextProjectId }));
  }, [currentProjectId, projectScope, projects]);

  useEffect(() => {
    void loadProjectInputs(selectedProjectId);
    const listProjectIds =
      projectScope === "project"
        ? selectedProjectId
          ? [selectedProjectId]
          : []
        : projects.filter((project) => !project.id.startsWith("__")).map((project) => project.id);
    void loadItems(listProjectIds);
  }, [loadItems, loadProjectInputs, projectScope, projects, selectedProjectId]);

  useEffect(() => {
    const hasActiveGeneration = itemSelection.rows.some((item) =>
      item.itemType === "set" && item.generation_run
        ? ACTIVE_GENERATION_STATUSES.has(item.generation_run.status)
        : false,
    );
    if (!hasActiveGeneration) {
      return;
    }
    const listProjectIds =
      projectScope === "project"
        ? selectedProjectId
          ? [selectedProjectId]
          : []
        : projects.filter((project) => !project.id.startsWith("__")).map((project) => project.id);
    if (listProjectIds.length === 0) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadItems(listProjectIds, { silent: true });
    }, TEST_CASE_SET_POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [itemSelection.rows, loadItems, projectScope, projects, selectedProjectId]);

  function openCreateDialog() {
    const nextProjectId =
      projectScope === "project" ? (currentProjectId ?? "") : form.projectId || projects[0]?.id || "";
    setCreateMode("case");
    setForm({ ...emptyForm, projectId: nextProjectId });
    setManualForm({
      ...emptyManualForm,
      projectId: nextProjectId,
      steps: [{ id: "step-1", action: "", expected_result: "" }],
    });
    setAiDescription("");
    setIncludeExplorationArtifacts(true);
    setPendingAiResult(null);
    setAiDialogOpen(false);
    setOverwriteDialogOpen(false);
    setDialogOpen(true);
  }

  function applyAiResult(result: ApiManualTestCaseAiGenerateResult) {
    setManualForm((current) => ({
      ...current,
      title: result.title,
      preconditions: result.preconditions,
      steps: result.steps.map((step, index) => ({
        id: `step-ai-${Date.now()}-${index}`,
        action: step.action,
        expected_result: step.expected_result,
      })),
      notes: current.notes,
    }));
    setPendingAiResult(null);
    setOverwriteDialogOpen(false);
    toast.success("AI 已生成测试用例，请检查后创建");
  }

  async function generateManualTestCaseWithAi() {
    if (!selectedManualProjectId) {
      toast.error("请选择项目");
      return;
    }
    const description = aiDescription.trim();
    if (description.length < 2) {
      toast.error("请输入测试描述");
      return;
    }
    setAiGenerating(true);
    try {
      const payload: ApiManualTestCaseAiGenerateRequest = {
        description,
        include_exploration_artifacts: includeExplorationArtifacts,
      };
      const result = await apiRequest<ApiManualTestCaseAiGenerateResult>(
        `/projects/${selectedManualProjectId}/test-cases/ai-generate`,
        { method: "POST", body: JSON.stringify(payload) },
      );
      setAiDialogOpen(false);
      if (manualFormHasContent(manualFormRef.current)) {
        setPendingAiResult(result);
        setOverwriteDialogOpen(true);
      } else {
        applyAiResult(result);
      }
    } finally {
      setAiGenerating(false);
    }
  }

  function addManualStep() {
    setManualForm((current) => ({
      ...current,
      steps: [...current.steps, { id: `step-${Date.now()}-${current.steps.length}`, action: "", expected_result: "" }],
    }));
  }

  function removeManualStep(index: number) {
    setManualForm((current) => ({
      ...current,
      steps:
        current.steps.length === 1
          ? [{ id: "step-1", action: "", expected_result: "" }]
          : current.steps.filter((_, stepIndex) => stepIndex !== index),
    }));
  }

  function updateManualStep(index: number, field: "action" | "expected_result", value: string) {
    setManualForm((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) => (stepIndex === index ? { ...step, [field]: value } : step)),
    }));
  }

  function handleRequirementChange(value: string) {
    const requirement = finalRequirements.find((item) => item.id === value);
    setForm((current) => ({
      ...current,
      requirementDocId: value,
      name: current.name || (requirement ? `${requirement.name}测试用例集` : current.name),
    }));
  }

  async function saveTestCaseSet() {
    if (!selectedProjectId) {
      toast.error("请选择项目");
      return;
    }
    if (!form.name.trim()) {
      toast.error("请填写用例集名称");
      return;
    }
    if (!form.requirementDocId) {
      toast.error("请选择需求");
      return;
    }
    if (form.generationScopeType === "specified" && !form.generationScopeText.trim()) {
      toast.error("请填写要生成的需求范围");
      return;
    }
    setSaving(true);
    try {
      const payload: ApiTestCaseSetCreate = {
        name: form.name.trim(),
        requirement_doc_id: form.requirementDocId,
        generation_scope_type: form.generationScopeType,
        generation_scope_text: form.generationScopeType === "specified" ? form.generationScopeText.trim() : "",
        notes: form.notes.trim(),
      };
      const created = await apiRequest<ApiTestCaseSet>(`/projects/${selectedProjectId}/test-case-sets`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      itemSelection.setRows((current) => [
        { ...created, itemType: "set" },
        ...current.filter((item) => item.id !== created.id),
      ]);
      setDialogOpen(false);
      toast.success("测试用例生成任务已创建");
      notifyAiTaskStarted();
    } finally {
      setSaving(false);
    }
  }

  async function saveManualTestCase() {
    if (!selectedManualProjectId) {
      toast.error("请选择项目");
      return;
    }
    if (!manualForm.title.trim()) {
      toast.error("请填写用例名称");
      return;
    }
    const steps = manualForm.steps.map(({ action, expected_result }) => ({
      action: action.trim(),
      expected_result: expected_result.trim(),
    }));
    if (steps.some((step) => !step.action || !step.expected_result)) {
      toast.error("请完整填写每一步的操作步骤和预期结果");
      return;
    }
    setSaving(true);
    try {
      const payload: ApiManualTestCaseCreate = {
        title: manualForm.title.trim(),
        preconditions: manualForm.preconditions.trim(),
        steps,
        notes: manualForm.notes.trim(),
      };
      const created = await apiRequest<ApiManualTestCase>(`/projects/${selectedManualProjectId}/test-cases`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      itemSelection.setRows((current) => [
        { ...created, itemType: "case" },
        ...current.filter((item) => item.id !== created.id),
      ]);
      setDialogOpen(false);
      toast.success("测试用例已创建");
    } finally {
      setSaving(false);
    }
  }

  async function deleteItems(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    try {
      await Promise.all(
        ids.map((id) => {
          const item = itemSelection.rows.find((row) => row.id === id);
          if (!item) {
            return Promise.resolve();
          }
          const resource = item.itemType === "case" ? "test-cases" : "test-case-sets";
          return apiRequest(`/projects/${item.project_id}/${resource}/${id}`, { method: "DELETE" });
        }),
      );
      itemSelection.setRows((current) => current.filter((row) => !ids.includes(row.id)));
      itemSelection.clearSelection();
      toast.success(`已删除 ${ids.length} 条测试用例数据`);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例删除失败");
    }
  }

  async function regenerateTestCaseSet(item: ApiTestCaseSet) {
    if (isTestCaseSetGenerating(item)) {
      return;
    }
    try {
      const regenerated = await apiRequest<ApiTestCaseSet>(
        `/projects/${item.project_id}/test-case-sets/${item.id}/regenerate`,
        { method: "POST" },
      );
      itemSelection.setRows((current) =>
        current.map((row) => (row.id === regenerated.id ? { ...regenerated, itemType: "set" } : row)),
      );
      toast.success("测试用例重新生成任务已创建");
      notifyAiTaskStarted();
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例重新生成失败");
    }
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("testCases")}
      description="查看测试用例集、生成状态和用例数量。"
      projectScope={projectScope}
      title="测试用例"
    >
      <ShellSection>
        <ListToolbar
          createLabel="新建用例"
          onBatchDelete={() => deleteItems(itemSelection.selectedIds)}
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索测试用例或用例集"
          selectedCount={itemSelection.selectedCount}
          title="测试用例列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部测试用例"
                    checked={itemSelection.allSelected || (itemSelection.partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => itemSelection.toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>名称</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>用例数量</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={7} label="测试用例加载中" /> : null}
              {!loading
                ? filteredRows.map((item) => (
                    <TableRow
                      data-state={itemSelection.selectedIds.includes(item.id) ? "selected" : undefined}
                      key={item.id}
                    >
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${item.itemType === "case" ? item.title : item.name}`}
                          checked={itemSelection.selectedIds.includes(item.id)}
                          onCheckedChange={(checked) => itemSelection.toggleOne(item.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        {item.itemType === "case" ? (
                          <Link
                            className="block truncate hover:underline"
                            href={`/test-cases/manual/${item.id}?project=${item.project_id}`}
                            title={item.title}
                          >
                            {item.title}
                          </Link>
                        ) : (
                          <Link
                            className="block truncate hover:underline"
                            href={`/test-cases/${item.id}/review?project=${item.project_id}`}
                            title={item.name}
                          >
                            {item.name}
                          </Link>
                        )}
                      </TableCell>
                      <TableCell>{item.itemType === "case" ? "测试用例" : "测试用例集"}</TableCell>
                      <TableCell>
                        <Badge
                          variant={item.itemType === "set" && item.status === "generating" ? "outline" : "secondary"}
                        >
                          {item.itemType === "case" ? (
                            "已创建"
                          ) : item.status === "generating" ? (
                            <ProcessingState label={testCaseSetStatusLabel(item)} />
                          ) : (
                            testCaseSetStatusLabel(item)
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell>{item.itemType === "case" ? 1 : item.case_count}</TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={
                            item.itemType === "case"
                              ? [
                                  {
                                    label: "查看",
                                    icon: ClipboardCheck,
                                    href: `/test-cases/manual/${item.id}?project=${item.project_id}`,
                                  },
                                  {
                                    label: "删除",
                                    icon: Trash2,
                                    destructive: true,
                                    onSelect: () => deleteItems([item.id]),
                                  },
                                ]
                              : [
                                  {
                                    label: "查看",
                                    icon: ClipboardCheck,
                                    href: `/test-cases/${item.id}/review?project=${item.project_id}`,
                                    disabled: item.case_count === 0 || isTestCaseSetGenerating(item),
                                  },
                                  {
                                    label: "重新生成",
                                    icon: RefreshCw,
                                    disabled: isTestCaseSetGenerating(item),
                                    onSelect: () => regenerateTestCaseSet(item),
                                  },
                                  {
                                    label: "删除",
                                    icon: Trash2,
                                    destructive: true,
                                    onSelect: () => deleteItems([item.id]),
                                  },
                                ]
                          }
                          label={`打开 ${item.itemType === "case" ? item.title : item.name} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                    暂无测试用例。可手工新建测试用例，或根据需求生成测试用例集。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setAiDialogOpen(false);
            setOverwriteDialogOpen(false);
            setPendingAiResult(null);
            setAiDescription("");
          }
        }}
      >
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-4xl">
          <DialogHeader className="shrink-0 px-6 pt-6">
            <div className="flex items-center justify-between gap-4 pr-6">
              <DialogTitle>新建测试用例</DialogTitle>
              {createMode === "case" ? (
                <Button
                  className="border-primary/20 bg-primary/[0.06] px-2.5 text-primary shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:border-primary/30 hover:bg-primary/10 hover:text-primary"
                  onClick={() => setAiDialogOpen(true)}
                  size="sm"
                  type="button"
                  variant="outline"
                >
                  <span className="flex size-5 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <Sparkles className="size-3.5" />
                  </span>
                  AI 生成
                </Button>
              ) : null}
            </div>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
            <Field className="sm:col-span-2">
              <FieldLabel>创建方式</FieldLabel>
              <RadioGroup
                className="grid gap-3 sm:grid-cols-2"
                onValueChange={(value) => setCreateMode(value as CreateMode)}
                value={createMode}
              >
                <Label
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 text-sm transition-colors ${
                    createMode === "case" ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                  }`}
                >
                  <RadioGroupItem value="case" />
                  新建测试用例
                </Label>
                <Label
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border p-4 text-sm transition-colors ${
                    createMode === "set" ? "border-primary bg-primary/5" : "hover:bg-muted/40"
                  }`}
                >
                  <RadioGroupItem value="set" />
                  新建测试用例集
                </Label>
              </RadioGroup>
            </Field>

            {createMode === "case" ? (
              <>
                <Field>
                  <FieldLabel htmlFor="manual-test-case-title">用例名称</FieldLabel>
                  <Input
                    id="manual-test-case-title"
                    onChange={(event) => setManualForm((current) => ({ ...current, title: event.target.value }))}
                    placeholder="请输入测试用例名称"
                    value={manualForm.title}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="manual-test-case-project">项目</FieldLabel>
                  <Select
                    disabled={projectScope === "project"}
                    placeholder={projectScope === "project" ? selectedProjectName || "当前项目" : "选择项目"}
                    setValue={(value) => setManualForm((current) => ({ ...current, projectId: value }))}
                    value={manualForm.projectId}
                  >
                    {projectScope === "project" && currentProjectId ? (
                      <SelectOption value={currentProjectId}>{selectedProjectName || "当前项目"}</SelectOption>
                    ) : (
                      projects.map((project) => (
                        <SelectOption key={project.id} value={project.id}>
                          {project.name}
                        </SelectOption>
                      ))
                    )}
                  </Select>
                </Field>
                <Field className="sm:col-span-2">
                  <FieldLabel>是否关联探索产物</FieldLabel>
                  <RadioGroup
                    className="flex gap-5"
                    onValueChange={(value) => setIncludeExplorationArtifacts(value === "yes")}
                    value={includeExplorationArtifacts ? "yes" : "no"}
                  >
                    <Label className="flex cursor-pointer items-center gap-2 text-sm">
                      <RadioGroupItem value="yes" />是
                    </Label>
                    <Label className="flex cursor-pointer items-center gap-2 text-sm">
                      <RadioGroupItem value="no" />否
                    </Label>
                  </RadioGroup>
                </Field>
                <Field className="sm:col-span-2">
                  <FieldLabel htmlFor="manual-test-case-preconditions">前置条件</FieldLabel>
                  <Textarea
                    className="min-h-9 resize-none overflow-hidden"
                    id="manual-test-case-preconditions"
                    onChange={(event) =>
                      setManualForm((current) => ({ ...current, preconditions: event.target.value }))
                    }
                    placeholder="请输入执行该用例前需要满足的条件"
                    rows={1}
                    value={manualForm.preconditions}
                  />
                </Field>
                <Field className="sm:col-span-2">
                  <div className="flex items-center justify-between gap-3">
                    <FieldLabel>测试步骤</FieldLabel>
                    <Button onClick={addManualStep} size="sm" type="button" variant="outline">
                      <Plus className="size-4" />
                      新增步骤
                    </Button>
                  </div>
                  <div className="overflow-hidden rounded-lg border">
                    <div className="grid grid-cols-[3rem_minmax(0,1fr)_minmax(0,1fr)_3rem] gap-3 border-b bg-muted/40 px-3 py-2 font-medium text-muted-foreground text-xs">
                      <span>序号</span>
                      <span>操作步骤</span>
                      <span>预期结果</span>
                      <span>操作</span>
                    </div>
                    <div className="divide-y">
                      {manualForm.steps.map((step, index) => (
                        <div
                          className="grid grid-cols-[3rem_minmax(0,1fr)_minmax(0,1fr)_3rem] items-start gap-3 p-3"
                          key={step.id}
                        >
                          <span className="pt-2 text-center text-muted-foreground text-sm">{index + 1}</span>
                          <Textarea
                            aria-label={`第 ${index + 1} 步操作步骤`}
                            className="min-h-9 resize-none overflow-hidden"
                            onChange={(event) => updateManualStep(index, "action", event.target.value)}
                            placeholder="请输入操作步骤"
                            rows={1}
                            value={step.action}
                          />
                          <Textarea
                            aria-label={`第 ${index + 1} 步预期结果`}
                            className="min-h-9 resize-none overflow-hidden"
                            onChange={(event) => updateManualStep(index, "expected_result", event.target.value)}
                            placeholder="请输入预期结果"
                            rows={1}
                            value={step.expected_result}
                          />
                          <Button
                            aria-label={`删除第 ${index + 1} 步`}
                            className="mt-1"
                            onClick={() => removeManualStep(index)}
                            size="icon"
                            type="button"
                            variant="ghost"
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                </Field>
                <Field className="sm:col-span-2">
                  <FieldLabel htmlFor="manual-test-case-notes">备注</FieldLabel>
                  <Textarea
                    className="min-h-9 resize-none overflow-hidden"
                    id="manual-test-case-notes"
                    onChange={(event) => setManualForm((current) => ({ ...current, notes: event.target.value }))}
                    placeholder="请输入补充说明"
                    rows={1}
                    value={manualForm.notes}
                  />
                </Field>
              </>
            ) : (
              <>
                <Field>
                  <FieldLabel htmlFor="test-case-set-name">用例集名称</FieldLabel>
                  <Input
                    id="test-case-set-name"
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    value={form.name}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="test-case-set-project">项目</FieldLabel>
                  <Select
                    disabled={projectScope === "project"}
                    placeholder={projectScope === "project" ? selectedProjectName || "当前项目" : "选择项目"}
                    setValue={(value) => setForm((current) => ({ ...current, projectId: value, requirementDocId: "" }))}
                    value={form.projectId}
                  >
                    {projectScope === "project" && currentProjectId ? (
                      <SelectOption value={currentProjectId}>{selectedProjectName || "当前项目"}</SelectOption>
                    ) : (
                      projects.map((project) => (
                        <SelectOption key={project.id} value={project.id}>
                          {project.name}
                        </SelectOption>
                      ))
                    )}
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="test-case-set-requirement">需求</FieldLabel>
                  <Select placeholder="选择需求" setValue={handleRequirementChange} value={form.requirementDocId}>
                    {finalRequirements.map((requirement) => (
                      <SelectOption key={requirement.id} value={requirement.id}>
                        {requirement.name}
                      </SelectOption>
                    ))}
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="test-case-set-exploration">使用探索产物</FieldLabel>
                  <Select
                    disabled
                    placeholder="暂未接入，后续开放。"
                    setValue={() => undefined}
                    value={NO_EXPLORATION_ARTIFACTS_VALUE}
                  >
                    <SelectOption value={NO_EXPLORATION_ARTIFACTS_VALUE}>不使用探索产物</SelectOption>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="test-case-set-company-knowledge">使用公司知识库</FieldLabel>
                  <Select
                    disabled
                    placeholder="暂未接入，后续开放。"
                    setValue={() => undefined}
                    value={NO_COMPANY_KNOWLEDGE_VALUE}
                  >
                    <SelectOption value={NO_COMPANY_KNOWLEDGE_VALUE}>不使用公司知识库</SelectOption>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel htmlFor="test-case-set-scope-type">生成范围</FieldLabel>
                  <Select
                    placeholder="选择生成范围"
                    setValue={(value) =>
                      setForm((current) => ({
                        ...current,
                        generationScopeType: value as ApiTestCaseGenerationScopeType,
                      }))
                    }
                    value={form.generationScopeType}
                  >
                    <SelectOption value="all">全部需求内容</SelectOption>
                    <SelectOption value="specified">指定范围</SelectOption>
                  </Select>
                </Field>
                {form.generationScopeType === "specified" ? (
                  <Field className="sm:col-span-2">
                    <FieldLabel htmlFor="test-case-set-scope-text">指定范围说明</FieldLabel>
                    <Textarea
                      className="min-h-20"
                      id="test-case-set-scope-text"
                      onChange={(event) =>
                        setForm((current) => ({ ...current, generationScopeText: event.target.value }))
                      }
                      placeholder="例如：这个需求中登录部分的测试用例"
                      value={form.generationScopeText}
                    />
                  </Field>
                ) : null}
                <Field className="sm:col-span-2">
                  <FieldLabel htmlFor="test-case-set-notes">备注</FieldLabel>
                  <Textarea
                    className="min-h-16"
                    id="test-case-set-notes"
                    onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                    placeholder="补充说明，不作为硬性生成范围"
                    value={form.notes}
                  />
                </Field>
              </>
            )}
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={saving}
              onClick={createMode === "case" ? saveManualTestCase : saveTestCaseSet}
              type="button"
            >
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              {createMode === "case" ? "创建测试用例" : "生成测试用例集"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={aiDialogOpen} onOpenChange={setAiDialogOpen}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>AI 生成测试用例</DialogTitle>
            <DialogDescription>描述希望验证的业务场景，AI 将生成完整测试用例。</DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="manual-test-case-ai-description">测试描述</FieldLabel>
            <Textarea
              className="min-h-32"
              id="manual-test-case-ai-description"
              maxLength={4000}
              onChange={(event) => setAiDescription(event.target.value)}
              placeholder="例如：验证用户连续输入错误密码达到限制次数后，账号会被锁定。"
              value={aiDescription}
            />
            <p className="text-muted-foreground text-xs">
              {includeExplorationArtifacts ? "生成依据：用户描述 + 当前项目全部探索产物" : "生成依据：用户描述"}
            </p>
          </Field>
          <DialogFooter>
            <Button disabled={aiGenerating} onClick={() => setAiDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={aiGenerating} onClick={generateManualTestCaseWithAi} type="button">
              {aiGenerating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              生成并填入
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={overwriteDialogOpen} onOpenChange={setOverwriteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>当前表单已有内容</AlertDialogTitle>
            <AlertDialogDescription>
              应用 AI 生成结果将覆盖已有的用例名称、前置条件和测试步骤，是否继续？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => pendingAiResult && applyAiResult(pendingAiResult)}>
              覆盖并应用
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}
