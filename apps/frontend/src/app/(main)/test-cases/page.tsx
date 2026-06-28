"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ClipboardCheck, Loader2, Play, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, MetricCard, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
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
  type ApiExplorationRun,
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
  explorationRunId: string;
  includeCompanyKnowledge: boolean;
  generationScopeType: ApiTestCaseGenerationScopeType;
  generationScopeText: string;
  notes: string;
};

const NO_EXPLORATION_VALUE = "__none__";
const ACTIVE_GENERATION_STATUSES = new Set(["queued", "running"]);
const TEST_CASE_SET_POLL_INTERVAL_MS = 5000;

const emptyForm: TestCaseSetForm = {
  name: "",
  projectId: "",
  requirementDocId: "",
  explorationRunId: "",
  includeCompanyKnowledge: true,
  generationScopeType: "all",
  generationScopeText: "",
  notes: "",
};

export default function Page() {
  const { scope: projectScope, currentProjectId, hydrate, hasHydrated } = useProjectContextStore();
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const setSelection = useLocalTableSelection<ApiTestCaseSet>([]);
  const [requirements, setRequirements] = useState<ApiRequirementDocument[]>([]);
  const [explorations, setExplorations] = useState<ApiExplorationRun[]>([]);
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

  const filteredRows = setSelection.rows.filter((item) =>
    [
      item.name,
      item.requirement_doc_title,
      item.exploration_run_title,
      item.status_label,
      item.generation_scope_text,
    ].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase())),
  );

  const relatedExplorations = useMemo(
    () => explorations.filter((item) => item.requirement_doc_id === form.requirementDocId),
    [explorations, form.requirementDocId],
  );

  const loadProjects = useCallback(async () => {
    const data = await apiRequest<ApiProject[]>("/projects");
    setProjects(data);
  }, []);

  const loadProjectInputs = useCallback(async (nextProjectId: string) => {
    if (!nextProjectId) {
      setRequirements([]);
      setExplorations([]);
      return;
    }
    const [nextRequirements, nextExplorations] = await Promise.all([
      apiRequest<ApiRequirementDocument[]>(`/projects/${nextProjectId}/requirements`),
      apiRequest<ApiExplorationRun[]>(`/page-exploration/runs?project_id=${nextProjectId}`),
    ]);
    setRequirements(nextRequirements);
    setExplorations(nextExplorations);
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
      explorationRunId: current.projectId === nextProjectId ? current.explorationRunId : "",
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

  function relatedExplorationForRequirement(requirementId: string) {
    return explorations.find(
      (item) => item.requirement_doc_id === requirementId && ["completed", "partial"].includes(item.status),
    );
  }

  function openCreateDialog() {
    const nextProjectId =
      projectScope === "project" ? (currentProjectId ?? "") : form.projectId || projects[0]?.id || "";
    setForm({ ...emptyForm, projectId: nextProjectId });
    setDialogOpen(true);
  }

  function handleRequirementChange(value: string) {
    const requirement = requirements.find((item) => item.id === value);
    const related = relatedExplorationForRequirement(value);
    setForm((current) => ({
      ...current,
      requirementDocId: value,
      name: current.name || (requirement ? `${requirement.name}测试用例集` : current.name),
      explorationRunId: related?.id ?? "",
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
        exploration_run_id: form.explorationRunId,
        include_company_knowledge: form.includeCompanyKnowledge,
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

  return (
    <PageShell
      breadcrumbs={["项目工作区", "测试用例"]}
      description="查看测试用例集、生成状态和用例数量。"
      projectScope={projectScope}
      title="测试用例"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          helper="当前项目测试用例集数量"
          icon={ClipboardCheck}
          label="测试用例集"
          value={String(setSelection.rows.length)}
        />
        <MetricCard
          helper="生成完成后展示待评审用例"
          icon={ClipboardCheck}
          label="测试用例"
          value={String(setSelection.rows.reduce((total, item) => total + item.case_count, 0))}
        />
        <MetricCard
          helper="生成中的用例集"
          icon={Loader2}
          label="生成中"
          value={String(setSelection.rows.filter((item) => item.status === "generating").length)}
        />
      </div>
      <ShellSection>
        <ListToolbar
          createLabel="新建测试用例集"
          onBatchDelete={() => deleteTestCaseSets(setSelection.selectedIds)}
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索用例集、需求或探索"
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
                <TableHead>关联探索</TableHead>
                <TableHead>生成范围</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>用例数量</TableHead>
                <TableHead>更新时间</TableHead>
                <TableHead className="w-16">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={9} label="测试用例集加载中" /> : null}
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
                      <TableCell className="font-medium">{item.name}</TableCell>
                      <TableCell>{item.requirement_doc_title}</TableCell>
                      <TableCell>{item.exploration_run_title || "不使用探索"}</TableCell>
                      <TableCell>
                        {item.generation_scope_type === "all" ? "全部需求内容" : item.generation_scope_text}
                      </TableCell>
                      <TableCell>
                        <Badge variant={item.status === "generating" ? "outline" : "secondary"}>
                          {item.status_label}
                        </Badge>
                      </TableCell>
                      <TableCell>{item.case_count}</TableCell>
                      <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                      <TableCell>
                        <RowActions
                          actions={[
                            { label: "查看", href: `/test-cases?set=${item.id}`, icon: Search },
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
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={9}>
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
            <DialogDescription>选择一个需求，配置探索、公司知识库和生成范围后生成测试用例。</DialogDescription>
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
                setValue={(value) =>
                  setForm((current) => ({ ...current, projectId: value, requirementDocId: "", explorationRunId: "" }))
                }
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
                {requirements.map((requirement) => (
                  <SelectOption key={requirement.id} value={requirement.id}>
                    {requirement.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-exploration">关联探索</FieldLabel>
              <Select
                placeholder="选择探索或不使用"
                setValue={(value) =>
                  setForm((current) => ({
                    ...current,
                    explorationRunId: value === NO_EXPLORATION_VALUE ? "" : value,
                  }))
                }
                value={form.explorationRunId || NO_EXPLORATION_VALUE}
              >
                <SelectOption value={NO_EXPLORATION_VALUE}>不使用探索</SelectOption>
                {(relatedExplorations.length > 0 ? relatedExplorations : explorations).map((exploration) => (
                  <SelectOption key={exploration.id} value={exploration.id}>
                    {exploration.title}
                  </SelectOption>
                ))}
              </Select>
              {relatedExplorations.length > 0 ? (
                <p className="text-muted-foreground text-xs">已根据所选需求自动选择关联探索，可手动调整。</p>
              ) : (
                <p className="text-muted-foreground text-xs">未找到关联探索，仍可基于需求和公司知识库生成。</p>
              )}
            </Field>
            <Field>
              <FieldLabel htmlFor="test-case-set-company-knowledge">使用公司知识库</FieldLabel>
              <div className="flex items-start gap-3 rounded-md border p-3 text-sm">
                <Checkbox
                  checked={form.includeCompanyKnowledge}
                  id="test-case-set-company-knowledge"
                  onCheckedChange={(checked) =>
                    setForm((current) => ({ ...current, includeCompanyKnowledge: Boolean(checked) }))
                  }
                />
                <span className="grid gap-1">
                  <span>默认开启</span>
                  <span className="text-muted-foreground text-xs">
                    用于查询通用测试规范、模板和术语。不确定的业务规则仍会标记为待确认。
                  </span>
                </span>
              </div>
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
