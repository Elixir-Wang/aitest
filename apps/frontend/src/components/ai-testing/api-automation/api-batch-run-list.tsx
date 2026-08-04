"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import { FileText, Pencil, Play, Trash2 } from "lucide-react";

import { ListToolbar, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiAutomationBatchRun,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioSuite,
  deleteApiAutomationScenarioSuite,
  formatDateTime,
  listApiAutomationEnvironments,
  listApiAutomationScenarioSuites,
  listApiAutomationScenarios,
  runApiAutomationScenarioSuite,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { ApiScenarioSuiteDialog } from "./api-scenario-suite-dialog";

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
  const [editingSuite, setEditingSuite] = useState<ApiAutomationScenarioSuite | null>(null);

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
    return suites.filter((suite) => `${suite.name} ${suite.description}`.toLowerCase().includes(keyword));
  }, [searchText, suites]);

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

  function openCreateDialog() {
    setEditingSuite(null);
    setDialogOpen(true);
  }

  function openEditDialog(suite: ApiAutomationScenarioSuite) {
    setEditingSuite(suite);
    setDialogOpen(true);
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
        placeholder="搜索测试集名称或描述"
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
              <TableHead className="w-[22%]">测试集名称</TableHead>
              <TableHead className="w-[27%]">描述</TableHead>
              <TableHead className="w-[10%]">场景数</TableHead>
              <TableHead className="w-[15%]">最近运行</TableHead>
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
                  <TableCell className="font-medium">
                    <Link
                      aria-label={`查看测试集 ${suite.name}`}
                      className="group inline-flex max-w-full items-center gap-1.5 rounded-sm outline-none transition-colors hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
                      href={`/projects/${projectId}/automation/api/suites/${suite.id}`}
                      title={suite.name}
                    >
                      <span className="truncate">{suite.name}</span>
                    </Link>
                  </TableCell>
                  <TableCell className="truncate text-muted-foreground" title={suite.description}>
                    {suite.description || "-"}
                  </TableCell>
                  <TableCell>{suite.scenarios.length}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {latestBatch ? (
                        <StatusBadge tone={batchTone(latestBatch)}>{batchLabel(latestBatch)}</StatusBadge>
                      ) : (
                        <span className="text-muted-foreground">未运行</span>
                      )}
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
                        ...(latestBatch?.status === "completed"
                          ? [{ label: "查看报告", icon: FileText, href: `/reports/api/${latestBatch.id}` }]
                          : []),
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
            {loading && filteredSuites.length === 0 ? <TableLoadingRow colSpan={7} label="测试集列表加载中" /> : null}
            {!loading && filteredSuites.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                  暂无场景测试集。新建后可重复运行，每次生成一份新报告。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <ApiScenarioSuiteDialog
        environments={environments}
        onOpenChange={setDialogOpen}
        onSaved={() => loadData()}
        open={dialogOpen}
        projectId={projectId}
        scenarios={scenarios}
        suite={editingSuite}
      />
    </ShellSection>
  );
}

function isRunnableSuiteScenario(scenario: ApiAutomationScenarioSuite["scenarios"][number]) {
  return scenario.revision > 0 && scenario.enabled_step_count > 0;
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
