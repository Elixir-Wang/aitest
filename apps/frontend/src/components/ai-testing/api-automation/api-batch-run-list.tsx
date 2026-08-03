"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { Eye, Pencil, Play, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
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
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationBatchRun,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioSuite,
  createApiAutomationScenarioSuite,
  deleteApiAutomationScenarioSuite,
  formatDateTime,
  listApiAutomationEnvironments,
  listApiAutomationScenarioSuites,
  listApiAutomationScenarios,
  runApiAutomationScenarioSuite,
  updateApiAutomationScenarioSuite,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

type ApiBatchRunListProps = {
  projectId: string;
};

export function ApiBatchRunList({ projectId }: ApiBatchRunListProps) {
  const [suites, setSuites] = useState<ApiAutomationScenarioSuite[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [scenarios, setScenarios] = useState<ApiAutomationScenario[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [runningSuiteId, setRunningSuiteId] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSuiteId, setEditingSuiteId] = useState("");
  const [suiteName, setSuiteName] = useState("");
  const [suiteDescription, setSuiteDescription] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([]);
  const [scenarioSearchText, setScenarioSearchText] = useState("");

  const loadData = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const [suiteRows, environmentRows, scenarioRows] = await Promise.all([
          listApiAutomationScenarioSuites(projectId),
          listApiAutomationEnvironments(projectId),
          listApiAutomationScenarios(projectId),
        ]);
        setSuites(suiteRows);
        setEnvironments(environmentRows);
        setScenarios(scenarioRows);
        setSelectedIds((current) => current.filter((id) => suiteRows.some((suite) => suite.id === id)));
      } catch (error) {
        if (!silent) toast.error(error instanceof Error ? error.message : "测试集列表加载失败");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [projectId],
  );

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const hasRunningBatch = suites.some(
      (suite) => suite.latest_batch?.status === "queued" || suite.latest_batch?.status === "running",
    );
    if (!hasRunningBatch) return;
    const timer = window.setInterval(() => void loadData(true), 2000);
    return () => window.clearInterval(timer);
  }, [loadData, suites]);

  const filteredSuites = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();
    if (!keyword) return suites;
    return suites.filter((suite) =>
      `${suite.name} ${suite.description} ${suite.environment?.name || ""}`.toLowerCase().includes(keyword),
    );
  }, [searchText, suites]);

  const filteredScenarios = useMemo(() => {
    const keyword = scenarioSearchText.trim().toLowerCase();
    if (!keyword) return scenarios;
    return scenarios.filter((scenario) => `${scenario.name} ${scenario.description}`.toLowerCase().includes(keyword));
  }, [scenarioSearchText, scenarios]);

  const visibleIds = filteredSuites.map((suite) => suite.id);
  const visibleSelectedIds = visibleIds.filter((id) => selectedIds.includes(id));
  const allSelected = visibleIds.length > 0 && visibleSelectedIds.length === visibleIds.length;
  const partiallySelected = visibleSelectedIds.length > 0 && !allSelected;

  function toggleOne(suiteId: string, checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...new Set([...current, suiteId])] : current.filter((id) => id !== suiteId),
    );
  }

  function toggleAll(checked: boolean) {
    setSelectedIds((current) =>
      checked ? [...new Set([...current, ...visibleIds])] : current.filter((id) => !visibleIds.includes(id)),
    );
  }

  function toggleScenario(scenarioId: string, checked: boolean) {
    setSelectedScenarioIds((current) =>
      checked ? [...new Set([...current, scenarioId])] : current.filter((id) => id !== scenarioId),
    );
  }

  function openCreateDialog() {
    setEditingSuiteId("");
    setSuiteName("");
    setSuiteDescription("");
    setEnvironmentId(environments[0]?.id || "");
    setSelectedScenarioIds([]);
    setScenarioSearchText("");
    setDialogOpen(true);
  }

  function openEditDialog(suite: ApiAutomationScenarioSuite) {
    setEditingSuiteId(suite.id);
    setSuiteName(suite.name);
    setSuiteDescription(suite.description);
    setEnvironmentId(suite.api_environment_id);
    setSelectedScenarioIds(suite.scenarios.map((scenario) => scenario.id));
    setScenarioSearchText("");
    setDialogOpen(true);
  }

  async function saveSuite() {
    if (!suiteName.trim() || !environmentId || selectedScenarioIds.length === 0) return;
    setBusy(true);
    try {
      const payload = {
        name: suiteName.trim(),
        description: suiteDescription.trim(),
        api_environment_id: environmentId,
        scenario_ids: selectedScenarioIds,
      };
      if (editingSuiteId) {
        await updateApiAutomationScenarioSuite(projectId, editingSuiteId, payload);
        toast.success("测试集已更新");
      } else {
        await createApiAutomationScenarioSuite(projectId, payload);
        toast.success("测试集已创建");
      }
      setDialogOpen(false);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试集保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSuites(ids: string[]) {
    if (ids.length === 0) return;
    setBusy(true);
    try {
      await Promise.all(ids.map((suiteId) => deleteApiAutomationScenarioSuite(projectId, suiteId)));
      setSelectedIds([]);
      await loadData();
      toast.success(`已删除 ${ids.length} 个测试集，历史报告不受影响`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试集删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function runSuite(suite: ApiAutomationScenarioSuite) {
    setRunningSuiteId(suite.id);
    try {
      const batch = await runApiAutomationScenarioSuite(projectId, suite.id);
      toast.success(`“${suite.name}”已开始运行，共 ${batch.counts.total} 个场景`);
      await loadData(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试集启动失败");
    } finally {
      setRunningSuiteId("");
    }
  }

  return (
    <ShellSection>
      <ListToolbar
        createDisabled={busy}
        createLabel="新建测试集"
        onBatchDelete={busy ? undefined : () => deleteSuites(visibleSelectedIds)}
        onCreate={openCreateDialog}
        onSearch={setSearchText}
        placeholder="搜索测试集名称、描述或环境"
        selectedCount={visibleSelectedIds.length}
        title="场景测试集"
      />
      <div className="overflow-hidden rounded-lg border">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[5%]">
                <Checkbox
                  aria-label="选择全部测试集"
                  checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                  disabled={busy || loading}
                  onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                />
              </TableHead>
              <TableHead className="w-[18%]">测试集名称</TableHead>
              <TableHead className="w-[22%]">描述</TableHead>
              <TableHead className="w-[14%]">环境</TableHead>
              <TableHead className="w-[9%]">场景数</TableHead>
              <TableHead className="w-[13%]">最近运行</TableHead>
              <TableHead className="w-[13%]">更新时间</TableHead>
              <TableHead className="w-[6%]">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredSuites.map((suite) => {
              const runnable = suite.scenarios.length > 0 && suite.scenarios.every(isRunnableSuiteScenario);
              const latestBatch = suite.latest_batch;
              return (
                <TableRow data-state={selectedIds.includes(suite.id) ? "selected" : undefined} key={suite.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`选择 ${suite.name}`}
                      checked={selectedIds.includes(suite.id)}
                      disabled={busy}
                      onCheckedChange={(checked) => toggleOne(suite.id, Boolean(checked))}
                    />
                  </TableCell>
                  <TableCell className="truncate font-medium" title={suite.name}>
                    {suite.name}
                  </TableCell>
                  <TableCell className="truncate text-muted-foreground" title={suite.description}>
                    {suite.description || "-"}
                  </TableCell>
                  <TableCell className="truncate" title={suite.environment?.api_base_url}>
                    {suite.environment?.name || "-"}
                  </TableCell>
                  <TableCell>{suite.scenarios.length}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {latestBatch ? (
                        <StatusBadge tone={batchTone(latestBatch)}>{batchLabel(latestBatch)}</StatusBadge>
                      ) : (
                        <span className="text-muted-foreground">未运行</span>
                      )}
                      {latestBatch?.status === "completed" ? (
                        <Button asChild size="icon" variant="ghost">
                          <Link aria-label={`查看 ${suite.name} 最近报告`} href={`/reports/api/${latestBatch.id}`}>
                            <Eye className="size-4" />
                          </Link>
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(suite.updated_at)}</TableCell>
                  <TableCell>
                    <RowActions
                      actions={[
                        {
                          label: "运行",
                          icon: Play,
                          disabled: busy || runningSuiteId === suite.id || !runnable,
                          onSelect: () => runSuite(suite),
                        },
                        { label: "编辑", icon: Pencil, disabled: busy, onSelect: () => openEditDialog(suite) },
                        {
                          label: "删除",
                          icon: Trash2,
                          destructive: true,
                          disabled: busy,
                          onSelect: () => deleteSuites([suite.id]),
                        },
                      ]}
                      label={`打开 ${suite.name} 操作菜单`}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
            {loading && filteredSuites.length === 0 ? <TableLoadingRow colSpan={8} label="测试集列表加载中" /> : null}
            {!loading && filteredSuites.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                  暂无场景测试集。新建后可重复运行，每次生成一份新报告。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <Dialog onOpenChange={(open) => !busy && setDialogOpen(open)} open={dialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>{editingSuiteId ? "编辑测试集" : "新建测试集"}</DialogTitle>
            <DialogDescription>
              选择一个接口环境和多个接口场景。同一场景只能加入一次，每次运行使用场景当前已保存内容。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="suite-name">测试集名称</FieldLabel>
                <Input
                  autoFocus
                  disabled={busy}
                  id="suite-name"
                  maxLength={100}
                  onChange={(event) => setSuiteName(event.target.value)}
                  placeholder="例如：核心接口冒烟"
                  value={suiteName}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="suite-environment">运行环境</FieldLabel>
                <Select
                  disabled={busy}
                  id="suite-environment"
                  placeholder="请选择运行环境"
                  setValue={setEnvironmentId}
                  value={environmentId}
                >
                  {environments.map((environment) => (
                    <SelectOption key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectOption>
                  ))}
                </Select>
              </Field>
            </div>
            <Field>
              <FieldLabel htmlFor="suite-description">测试集描述</FieldLabel>
              <Textarea
                disabled={busy}
                id="suite-description"
                maxLength={500}
                onChange={(event) => setSuiteDescription(event.target.value)}
                placeholder="请输入测试集描述（选填）"
                value={suiteDescription}
              />
            </Field>
            <Field>
              <div className="flex items-center justify-between gap-3">
                <FieldLabel htmlFor="suite-scenario-search">接口场景</FieldLabel>
                <span className="text-muted-foreground text-xs">已选择 {selectedScenarioIds.length} 个</span>
              </div>
              <Input
                disabled={busy}
                id="suite-scenario-search"
                onChange={(event) => setScenarioSearchText(event.target.value)}
                placeholder="搜索场景名称或描述"
                value={scenarioSearchText}
              />
              <div className="max-h-72 overflow-y-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12" />
                      <TableHead>场景名称</TableHead>
                      <TableHead className="w-24">启用步骤</TableHead>
                      <TableHead className="w-28">状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredScenarios.map((scenario) => {
                      const runnable = isRunnableScenario(scenario);
                      return (
                        <TableRow key={scenario.id}>
                          <TableCell>
                            <Checkbox
                              aria-label={`选择场景 ${scenario.name}`}
                              checked={selectedScenarioIds.includes(scenario.id)}
                              disabled={busy || !runnable}
                              onCheckedChange={(checked) => toggleScenario(scenario.id, Boolean(checked))}
                            />
                          </TableCell>
                          <TableCell>
                            <p className="font-medium">{scenario.name}</p>
                            <p className="line-clamp-1 text-muted-foreground text-xs">{scenario.description || "-"}</p>
                          </TableCell>
                          <TableCell>{scenario.steps.filter((step) => step.enabled).length}</TableCell>
                          <TableCell>
                            <StatusBadge tone={runnable ? "success" : "warning"}>
                              {runnable ? "可运行" : "请先保存场景"}
                            </StatusBadge>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                    {filteredScenarios.length === 0 ? (
                      <TableRow>
                        <TableCell className="h-20 text-center text-muted-foreground" colSpan={4}>
                          暂无匹配的接口场景。
                        </TableCell>
                      </TableRow>
                    ) : null}
                  </TableBody>
                </Table>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button disabled={busy} onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={busy || !suiteName.trim() || !environmentId || selectedScenarioIds.length === 0}
              onClick={saveSuite}
              type="button"
            >
              {busy ? "保存中..." : "保存测试集"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ShellSection>
  );
}

function isRunnableScenario(scenario: ApiAutomationScenario) {
  return scenario.status === "ready" && scenario.steps.some((step) => step.enabled);
}

function isRunnableSuiteScenario(scenario: ApiAutomationScenarioSuite["scenarios"][number]) {
  return scenario.status === "ready" && scenario.enabled_step_count > 0;
}

function batchLabel(batch: ApiAutomationBatchRun) {
  if (batch.status === "queued") return "排队中";
  if (batch.status === "running") return "运行中";
  if (batch.status === "failed") return "启动失败";
  if (batch.result === "passed") return "通过";
  if (batch.result === "observed") return "待确认";
  if (batch.result === "failed") return "失败";
  if (batch.result === "error") return "异常";
  return "已完成";
}

function batchTone(batch: ApiAutomationBatchRun): StatusBadgeTone {
  if (batch.status === "queued" || batch.status === "running") return "processing";
  if (batch.status === "failed" || batch.result === "failed" || batch.result === "error") return "destructive";
  if (batch.result === "observed") return "warning";
  return "success";
}
