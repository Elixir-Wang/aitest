"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { ClipboardCheck, Loader2, Play, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { ProcessingState, TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import {
  type ApiProject,
  type ApiRequirementDocument,
  type ApiTestCaseGenerationScopeType,
  type ApiTestCaseSet,
  type ApiTestCaseSetCreate,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

type TestCaseSetForm = {
  name: string;
  projectId: string;
  requirementDocId: string;
  generationScopeType: ApiTestCaseGenerationScopeType;
  generationScopeText: string;
  notes: string;
};

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

export default function Page() {
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const setSelection = useLocalTableSelection<ApiTestCaseSet>([]);
  const [requirements, setRequirements] = useState<ApiRequirementDocument[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<TestCaseSetForm>({ ...emptyForm });

  useEffect(() => {
    if (!hasHydrated) {
      hydrate();
    }
  }, [hasHydrated, hydrate]);

  const selectedProjectId = projectScope === "project" ? (currentProjectId ?? "") : form.projectId;
  const currentProjectName =
    projectScope === "project" ? (projects.find((item) => item.id === currentProjectId)?.name ?? "") : "";
  const selectedProjectName =
    projectScope === "project" ? currentProjectName : (projects.find((item) => item.id === form.projectId)?.name ?? "");
  const finalRequirements = requirements.filter(isFinalRequirement);

  const filteredRows = setSelection.rows.filter((item) =>
    [item.name, item.requirement_doc_title, testCaseSetStatusLabel(item), item.generation_scope_text].some((value) =>
      value.toLowerCase().includes(searchText.trim().toLowerCase()),
    ),
  );

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

  const loadSets = useCallback(
    async (nextProjectIds: string[], options?: { silent?: boolean }) => {
      if (nextProjectIds.length === 0) {
        setSelection.setRows([]);
        setLoading(false);
        return;
      }
      if (!options?.silent) {
        setLoading(true);
      }
      try {
        const data = await Promise.all(
          nextProjectIds.map((projectId) => apiRequest<ApiTestCaseSet[]>(`/projects/${projectId}/test-case-sets`)),
        );
        setSelection.setRows(data.flat().sort((first, second) => second.updated_at.localeCompare(first.updated_at)));
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [setSelection.setRows],
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
  }, [currentProjectId, projectScope, projects]);

  useEffect(() => {
    void loadProjectInputs(selectedProjectId);
    const listProjectIds =
      projectScope === "project"
        ? selectedProjectId
          ? [selectedProjectId]
          : []
        : projects.filter((project) => !project.id.startsWith("__")).map((project) => project.id);
    void loadSets(listProjectIds);
  }, [loadProjectInputs, loadSets, projectScope, projects, selectedProjectId]);

  useEffect(() => {
    const hasActiveGeneration = setSelection.rows.some((item) =>
      item.generation_run ? ACTIVE_GENERATION_STATUSES.has(item.generation_run.status) : false,
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
      void loadSets(listProjectIds, { silent: true });
    }, TEST_CASE_SET_POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [loadSets, projectScope, projects, selectedProjectId, setSelection.rows]);

  function openCreateDialog() {
    const nextProjectId =
      projectScope === "project" ? (currentProjectId ?? "") : form.projectId || projects[0]?.id || "";
    setForm({ ...emptyForm, projectId: nextProjectId });
    setDialogOpen(true);
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
      setSelection.setRows((current) => [created, ...current.filter((item) => item.id !== created.id)]);
      setDialogOpen(false);
      toast.success("测试用例生成任务已创建");
      notifyAiTaskStarted();
    } finally {
      setSaving(false);
    }
  }

  async function deleteTestCaseSets(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    try {
      await Promise.all(
        ids.map((id) => {
          const item = setSelection.rows.find((row) => row.id === id);
          if (!item) {
            return Promise.resolve();
          }
          return apiRequest(`/projects/${item.project_id}/test-case-sets/${id}`, { method: "DELETE" });
        }),
      );
      setSelection.setRows((current) => current.filter((row) => !ids.includes(row.id)));
      setSelection.clearSelection();
      toast.success(`已删除 ${ids.length} 个测试用例集`);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "测试用例集删除失败");
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
      setSelection.setRows((current) => current.map((row) => (row.id === regenerated.id ? regenerated : row)));
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
          createLabel="新建测试用例集"
          onBatchDelete={() => deleteTestCaseSets(setSelection.selectedIds)}
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索用例集或需求"
          selectedCount={setSelection.selectedCount}
          title="测试用例集列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部测试用例集"
                    checked={setSelection.allSelected || (setSelection.partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => setSelection.toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用例集名称</TableHead>
                <TableHead>需求</TableHead>
                <TableHead>生成范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>用例数量</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={8} label="测试用例集加载中" /> : null}
              {!loading
                ? filteredRows.map((item) => (
                    <TableRow
                      data-state={setSelection.selectedIds.includes(item.id) ? "selected" : undefined}
                      key={item.id}
                    >
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${item.name}`}
                          checked={setSelection.selectedIds.includes(item.id)}
                          onCheckedChange={(checked) => setSelection.toggleOne(item.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        <Link
                          className="block truncate hover:underline"
                          href={`/test-cases/${item.id}/review?project=${item.project_id}`}
                          title={item.name}
                        >
                          {item.name}
                        </Link>
                      </TableCell>
                      <TableCell>{item.requirement_doc_title}</TableCell>
                      <TableCell>
                        {item.generation_scope_type === "all" ? "全部需求内容" : item.generation_scope_text}
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.status === "generating" ? "outline" : "secondary"}>
                          {item.status === "generating" ? (
                            <ProcessingState label={testCaseSetStatusLabel(item)} />
                          ) : (
                            testCaseSetStatusLabel(item)
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell>{item.case_count}</TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
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
                              onSelect: () => deleteTestCaseSets([item.id]),
                            },
                          ]}
                          label={`打开 ${item.name} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))
                : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                    暂无测试用例。可新建测试用例集，选择需求后生成测试用例。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>新建测试用例集</DialogTitle>
            <DialogDescription>选择一个需求，配置生成范围后生成测试用例。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
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
                  onChange={(event) => setForm((current) => ({ ...current, generationScopeText: event.target.value }))}
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
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={saving} onClick={saveTestCaseSet} type="button">
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              生成测试用例
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
