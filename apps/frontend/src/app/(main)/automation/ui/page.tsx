"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { Loader2, Play, Plus, X } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiManualTestCase,
  type ApiProject,
  type ApiTestCase,
  type ApiTestCaseSet,
  apiRequest,
  createUiAutomationExecutionRun,
  createUiAutomationGenerationRun,
  getUiAutomationGenerationRun,
  listUiAutomationAssets,
  listUiAutomationGenerationRuns,
  type UiAutomationAsset,
  type UiAutomationGenerationRun,
} from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

type Operation = {
  key: string;
  status: string;
  page_path: string;
  steps: Array<{ action: string; element_key: string }>;
};

type UiAutomationRow = {
  id: string;
  project: ApiProject;
  testCase: ApiManualTestCase | ApiTestCase | null;
  operation: Operation | null;
  asset?: UiAutomationAsset;
  generationRun?: UiAutomationGenerationRun;
};

const statusLabels: Record<string, string> = {
  queued: "排队中",
  pending: "待处理",
  running: "执行中",
  completed: "已完成",
  passed: "通过",
  failed: "失败",
  ready: "可执行",
  waiting_manual: "等待人工处理",
  degraded: "需要重新生成",
  deprecated: "已废弃",
};

function labelForStatus(status: string) {
  return statusLabels[status] ?? status;
}

export default function Page() {
  const selection = useLocalTableSelection<UiAutomationRow>([]);
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [createEnvironments, setCreateEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [sourceCases, setSourceCases] = useState<Array<ApiManualTestCase | ApiTestCase>>([]);
  const [executionRow, setExecutionRow] = useState<UiAutomationRow | null>(null);
  const [executionEnvironments, setExecutionEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [executionEnvironmentId, setExecutionEnvironmentId] = useState("");
  const [executionLoading, setExecutionLoading] = useState(false);

  const activeProjects = projects.filter((project) => project.status === "active");
  const filteredRows = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    return selection.rows.filter((row) => {
      if (!query) return true;
      return [
        row.testCase?.title,
        row.operation?.key,
        row.operation?.page_path,
        row.asset?.test_file_path,
        row.generationRun?.id,
      ]
        .filter(Boolean)
        .some((value) => value?.toLowerCase().includes(query));
    });
  }, [searchText, selection.rows]);

  const loadProjectRows = useCallback(
    async (nextProjects: ApiProject[]) => {
      const active = nextProjects.filter((project) => project.status === "active");
      const projectRows = await Promise.all(
        active.map(async (project) => {
          const [assets, generationRuns, operationsArtifact, testCaseSets, manualTestCases] = await Promise.all([
            listUiAutomationAssets(project.id),
            listUiAutomationGenerationRuns(project.id),
            apiRequest<{ operations: Operation[] }>(`/page-exploration/projects/${project.id}/operations`),
            apiRequest<ApiTestCaseSet[]>(`/projects/${project.id}/test-case-sets`),
            apiRequest<ApiManualTestCase[]>(`/projects/${project.id}/test-cases`),
          ]);
          const detailedSets = await Promise.all(
            testCaseSets.map((set) => apiRequest<ApiTestCaseSet>(`/projects/${project.id}/test-case-sets/${set.id}`)),
          );
          const cases = [
            ...manualTestCases,
            ...detailedSets.flatMap((set) => set.cases ?? []).filter((item) => item.status === "approved"),
          ];
          const assetRows = assets.map((asset) => {
            const testCase = cases.find((item) => item.id === asset.test_case_id) ?? null;
            const operation =
              operationsArtifact.operations?.find(
                (item) =>
                  asset.pytest_node_id.includes(item.key) ||
                  Boolean(testCase?.title && item.key.includes(testCase.title)),
              ) ?? null;
            return { id: asset.id, asset, project, testCase, operation };
          });
          const generationRows = generationRuns
            .filter(
              (generationRun) =>
                !assets.some((asset) => asset.generation_run_id === generationRun.id) &&
                generationRun.status !== "completed",
            )
            .map((generationRun) => ({
              id: generationRun.id,
              generationRun,
              project,
              testCase: cases.find((item) => item.id === generationRun.test_case_id) ?? null,
              operation: null,
            }));
          return [...generationRows, ...assetRows];
        }),
      );
      selection.setRows(projectRows.flat());
    },
    [selection.setRows],
  );

  const loadCases = useCallback(async (nextProjectId: string) => {
    if (!nextProjectId) {
      setSourceCases([]);
      return;
    }
    const sets = await apiRequest<ApiTestCaseSet[]>(`/projects/${nextProjectId}/test-case-sets`);
    const details = await Promise.all(
      sets.map((set) => apiRequest<ApiTestCaseSet>(`/projects/${nextProjectId}/test-case-sets/${set.id}`)),
    );
    const manual = await apiRequest<ApiManualTestCase[]>(`/projects/${nextProjectId}/test-cases`);
    const approved = details.flatMap((set) => set.cases ?? []).filter((item) => item.status === "approved");
    setSourceCases([...manual, ...approved]);
  }, []);

  useEffect(() => {
    async function loadInitialData() {
      setLoading(true);
      try {
        const nextProjects = await apiRequest<ApiProject[]>("/projects");
        setProjects(nextProjects);
        await loadProjectRows(nextProjects);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "UI 自动化数据加载失败");
      } finally {
        setLoading(false);
      }
    }
    void loadInitialData();
  }, [loadProjectRows]);

  function openCreateDialog() {
    const defaultProjectId = activeProjects[0]?.id || "";
    setSelectedProjectId(defaultProjectId);
    setSelectedEnvironmentId("");
    setCreateEnvironments([]);
    setSelectedSource("");
    setDialogOpen(true);
    if (defaultProjectId) {
      void Promise.all([
        loadCases(defaultProjectId),
        apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${defaultProjectId}`),
      ])
        .then(([, environmentItems]) => {
          setCreateEnvironments(environmentItems);
          setSelectedEnvironmentId(environmentItems[0]?.id ?? "");
        })
        .catch((error) => toast.error(error instanceof Error ? error.message : "新建数据加载失败"));
    }
  }

  async function createGeneration() {
    if (!selectedProjectId || !selectedSource || !selectedEnvironmentId) {
      toast.error("请选择项目、测试用例和运行环境");
      return;
    }
    setSaving(true);
    try {
      const created = await createUiAutomationGenerationRun(selectedProjectId, {
        test_case_id: selectedSource,
        environment_id: selectedEnvironmentId,
      });
      setDialogOpen(false);
      toast.success("已创建 UI 自动化生成任务");
      await loadProjectRows(projects);
      void pollGeneration(selectedProjectId, created.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "UI 自动化生成失败");
    } finally {
      setSaving(false);
    }
  }

  async function pollGeneration(projectId: string, runId: string) {
    try {
      const next = await getUiAutomationGenerationRun(projectId, runId);
      if (["queued", "running"].includes(next.status)) {
        window.setTimeout(() => void pollGeneration(projectId, runId), 1000);
        return;
      }
      await loadProjectRows(projects);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "UI 自动化生成状态刷新失败");
    }
  }

  async function openExecutionDialog(row: UiAutomationRow) {
    setExecutionRow(row);
    setExecutionLoading(true);
    setExecutionEnvironments([]);
    setExecutionEnvironmentId("");
    try {
      const environmentItems = await apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${row.project.id}`);
      setExecutionEnvironments(environmentItems);
      setExecutionEnvironmentId(environmentItems[0]?.id ?? "");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "运行环境加载失败");
    } finally {
      setExecutionLoading(false);
    }
  }

  async function executeAsset() {
    if (!executionRow?.asset || !executionEnvironmentId) {
      toast.error("请选择运行环境");
      return;
    }
    try {
      const created = await createUiAutomationExecutionRun(
        executionRow.project.id,
        executionRow.asset.id,
        executionEnvironmentId,
      );
      setExecutionRow(null);
      window.location.assign(
        `/projects/${executionRow.project.id}/automation/ui/assets/${executionRow.asset.id}/runs/${created.id}`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "UI 自动化执行失败");
    }
  }

  const selectedProjectEnvironments = createEnvironments.filter((item) => item.project_id === selectedProjectId);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("uiAutomation")}
      description="查看已生成的 UI 自动化用例，并在项目环境中执行。"
      projectScope="all"
      title="UI 自动化"
    >
      <ShellSection>
        <ListToolbar
          createLabel="新建 UI 自动化"
          onCreate={openCreateDialog}
          onSearch={setSearchText}
          placeholder="搜索用例名称、入口路径或自动化文件"
          selectedCount={selection.selectedCount}
          title="UI 自动化列表"
        />
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox
                    aria-label="选择全部 UI 自动化用例"
                    checked={selection.allSelected || (selection.partiallySelected ? "indeterminate" : false)}
                    disabled={loading}
                    onCheckedChange={(checked) => selection.toggleAll(Boolean(checked))}
                  />
                </TableHead>
                <TableHead>用例名称</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>入口路径</TableHead>
                <TableHead>步骤</TableHead>
                <TableHead className="w-20">执行</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? <TableLoadingRow colSpan={6} label="UI 自动化列表加载中" /> : null}
              {!loading
                ? filteredRows.map((row) => (
                    <TableRow data-state={selection.selectedIds.includes(row.id) ? "selected" : undefined} key={row.id}>
                      <TableCell>
                        <Checkbox
                          aria-label={`选择 ${row.testCase?.title ?? row.asset?.id ?? row.generationRun?.id}`}
                          checked={selection.selectedIds.includes(row.id)}
                          disabled={Boolean(row.generationRun)}
                          onCheckedChange={(checked) => selection.toggleOne(row.id, Boolean(checked))}
                        />
                      </TableCell>
                      <TableCell className="max-w-72 truncate font-medium">
                        {row.asset ? (
                          <Link
                            className="block truncate text-foreground hover:text-primary hover:underline"
                            href={`/projects/${row.project.id}/automation/ui/assets/${row.asset.id}`}
                            title={row.testCase?.title ?? row.asset.test_file_path}
                          >
                            {row.testCase?.title ?? row.asset.test_file_path}
                          </Link>
                        ) : (
                          <span className="block truncate" title={row.testCase?.title ?? row.generationRun?.id}>
                            {row.testCase?.title ?? "UI 自动化生成任务"}
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusBadge
                          title={row.generationRun?.error_message || undefined}
                          tone={chineseCompletionTone(row.asset?.status ?? row.generationRun?.status ?? "")}
                        >
                          {labelForStatus(row.asset?.status ?? row.generationRun?.status ?? "")}
                        </StatusBadge>
                      </TableCell>
                      <TableCell
                        className="max-w-64 truncate font-mono text-xs"
                        title={row.operation?.page_path ?? row.asset?.suite_path ?? row.generationRun?.suite_path}
                      >
                        {row.operation?.page_path ?? row.asset?.suite_path ?? "生成任务"}
                      </TableCell>
                      <TableCell>{row.operation?.steps.length ?? row.testCase?.steps.length ?? "-"}</TableCell>
                      <TableCell>
                        <Button
                          aria-label={`执行 ${row.testCase?.title ?? row.asset?.id ?? row.generationRun?.id}`}
                          disabled={!row.asset || ["degraded", "deprecated"].includes(row.asset.status)}
                          onClick={() => void openExecutionDialog(row)}
                          size="icon-sm"
                        >
                          <Play className="size-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                : null}
              {!loading && filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                    暂无 UI 自动化资产。可新建 UI 自动化后从已采纳测试用例生成。
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </div>
      </ShellSection>

      <Dialog
        open={Boolean(executionRow)}
        onOpenChange={(open) => {
          if (!open) setExecutionRow(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>执行 UI 自动化</DialogTitle>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="ui-automation-run-environment">运行环境</FieldLabel>
            <Select
              placeholder={executionLoading ? "运行环境加载中" : "选择运行环境"}
              setValue={setExecutionEnvironmentId}
              value={executionEnvironmentId}
            >
              {executionEnvironments.map((environment) => (
                <SelectOption key={environment.id} value={environment.id}>
                  {environment.name}
                </SelectOption>
              ))}
            </Select>
          </Field>
          <DialogFooter>
            <Button onClick={() => setExecutionRow(null)} type="button" variant="outline">
              <X className="size-4" />
              取消
            </Button>
            <Button
              disabled={executionLoading || !executionEnvironmentId}
              onClick={() => void executeAsset()}
              type="button"
            >
              <Play className="size-4" />
              开始执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>新建 UI 自动化</DialogTitle>
          </DialogHeader>
          <FieldGroup className="overflow-y-auto px-6 py-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="ui-automation-project">项目</FieldLabel>
              <Select
                placeholder="选择项目"
                setValue={(value) => {
                  setSelectedProjectId(value);
                  setSelectedSource("");
                  setSelectedEnvironmentId("");
                  void loadCases(value);
                  void apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${value}`)
                    .then((environmentItems) => {
                      setCreateEnvironments(environmentItems);
                      setSelectedEnvironmentId(environmentItems[0]?.id ?? "");
                    })
                    .catch((error) => toast.error(error instanceof Error ? error.message : "项目环境加载失败"));
                }}
                value={selectedProjectId}
              >
                {activeProjects.map((project) => (
                  <SelectOption key={project.id} value={project.id}>
                    {project.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="ui-automation-source">测试用例</FieldLabel>
              <Select placeholder="选择测试用例" setValue={setSelectedSource} value={selectedSource}>
                {sourceCases.map((testCase) => (
                  <SelectOption key={testCase.id} value={testCase.id}>
                    {testCase.title}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="ui-automation-environment">运行环境</FieldLabel>
              <Select placeholder="选择项目环境" setValue={setSelectedEnvironmentId} value={selectedEnvironmentId}>
                {selectedProjectEnvironments.map((environment) => (
                  <SelectOption key={environment.id} value={environment.id}>
                    {environment.name}
                  </SelectOption>
                ))}
              </Select>
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              <X className="size-4" />
              取消
            </Button>
            <Button disabled={saving} onClick={() => void createGeneration()} type="button">
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
