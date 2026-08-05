"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  Code2,
  Database,
  FileJson,
  FileText,
  Gauge,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Trash2,
  Workflow,
  XCircle,
} from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
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
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  apiRequest,
  createUiAutomationExecutionRun,
  createUiAutomationRevisionRun,
  deleteUiAutomationExecutionRun,
  formatDateTime,
  getUiAutomationAsset,
  listUiAutomationAssetExecutionRuns,
  listUiAutomationAssetGenerationRuns,
  type UiAutomationAsset,
  type UiAutomationExecutionRun,
  type UiAutomationGenerationRun,
} from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const MAIN_TABS = ["overview", "runs"] as const;
type MainTab = (typeof MAIN_TABS)[number];
const ACTIVE_EXECUTION_STATUSES = new Set(["queued", "running"]);

const statusLabels: Record<string, string> = {
  queued: "排队中",
  running: "执行中",
  completed: "已生成",
  waiting_manual: "等待人工处理",
  failed: "失败",
  cancelled: "已取消",
  passed: "通过",
  ready: "可执行",
  degraded: "需要重新生成",
  deprecated: "已废弃",
};

const generationStages = [
  { key: "queued", label: "生成任务", icon: Workflow },
  { key: "completed", label: "资产校验", icon: ShieldCheck },
  { key: "passed", label: "真实执行", icon: Play },
] as const;

function EnvironmentPanel({
  environmentId,
  environments,
  loading,
  onEnvironmentChange,
}: {
  environmentId: string;
  environments: ExplorationEnvironment[];
  loading: boolean;
  onEnvironmentChange: (value: string) => void;
}) {
  return (
    <section className="border bg-card p-5">
      <SectionEyebrow icon={Gauge} label="运行环境" />
      <Field className="mt-5">
        <FieldLabel htmlFor="ui-asset-run-environment">运行环境</FieldLabel>
        <Select
          id="ui-asset-run-environment"
          placeholder={loading ? "运行环境加载中" : "选择运行环境"}
          setValue={onEnvironmentChange}
          value={environmentId}
        >
          {environments.map((environment) => (
            <SelectOption key={environment.id} value={environment.id}>
              {environment.name}
            </SelectOption>
          ))}
        </Select>
      </Field>
    </section>
  );
}

export function UiAutomationAssetDetail({ projectId, assetId }: { projectId: string; assetId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: MainTab = MAIN_TABS.includes(requestedTab as MainTab) ? (requestedTab as MainTab) : "overview";
  const [asset, setAsset] = useState<UiAutomationAsset | null>(null);
  const [generationRuns, setGenerationRuns] = useState<UiAutomationGenerationRun[]>([]);
  const [executionRuns, setExecutionRuns] = useState<UiAutomationExecutionRun[]>([]);
  const [environments, setEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [executionEnvironmentId, setExecutionEnvironmentId] = useState("");
  const [executeLoading, setExecuteLoading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [revisionDialogOpen, setRevisionDialogOpen] = useState(false);
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [runAfterRevision, setRunAfterRevision] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingRuns, setDeletingRuns] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadDetail = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const [nextAsset, nextGenerationRuns, nextExecutionRuns, nextEnvironments] = await Promise.all([
          getUiAutomationAsset(projectId, assetId),
          listUiAutomationAssetGenerationRuns(projectId, assetId),
          listUiAutomationAssetExecutionRuns(projectId, assetId),
          apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${projectId}`).catch(() => []),
        ]);
        setAsset(nextAsset);
        setGenerationRuns(nextGenerationRuns);
        setExecutionRuns(nextExecutionRuns);
        setSelectedRunIds((current) =>
          current.filter((id) =>
            nextExecutionRuns.some((run) => run.id === id && !ACTIVE_EXECUTION_STATUSES.has(run.status)),
          ),
        );
        setEnvironments(nextEnvironments);
        setExecutionEnvironmentId((current) => {
          if (nextEnvironments.some((environment) => environment.id === current)) return current;
          const recentEnvironmentId = nextGenerationRuns[0]?.environment_id;
          if (nextEnvironments.some((environment) => environment.id === recentEnvironmentId)) {
            return recentEnvironmentId;
          }
          return nextEnvironments[0]?.id ?? "";
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "UI 自动化资产加载失败");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [assetId, projectId],
  );

  useEffect(() => void loadDetail(), [loadDetail]);

  const latestGeneration = generationRuns[0] ?? asset?.latest_generation_run ?? null;
  const latestExecution = executionRuns[0] ?? asset?.latest_execution_run ?? null;
  const locatorRequired = asset?.locator_summary?.required ?? 0;
  const locatorAvailable = asset?.locator_summary?.available ?? 0;
  const locatorReady = locatorRequired === 0 || locatorAvailable >= locatorRequired;
  const canExecute = asset?.status === "ready" && executionEnvironmentId.length > 0 && !executeLoading;
  const stats = useMemo(
    () => ({
      total: executionRuns.length,
      passed: executionRuns.filter((run) => run.status === "passed").length,
      failed: executionRuns.filter((run) => run.status === "failed").length,
    }),
    [executionRuns],
  );

  function setActiveTab(tab: string) {
    router.replace(`/projects/${projectId}/automation/ui/assets/${assetId}?tab=${tab}`, { scroll: false });
  }

  async function execute() {
    if (!executionEnvironmentId) {
      toast.error("请选择运行环境");
      return;
    }
    setExecuteLoading(true);
    try {
      const run = await createUiAutomationExecutionRun(projectId, assetId, executionEnvironmentId);
      router.push(`/projects/${projectId}/automation/ui/assets/${assetId}/runs/${run.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "UI 自动化执行失败");
    } finally {
      setExecuteLoading(false);
    }
  }

  function openRevisionDialog() {
    if (!asset || !latestGeneration?.environment_id) {
      toast.error("缺少最近生成环境，无法进行 AI 修改");
      return;
    }
    setRevisionInstruction("");
    setRunAfterRevision(false);
    setRevisionDialogOpen(true);
  }

  async function submitRevision() {
    if (!asset || !latestGeneration?.environment_id) {
      toast.error("缺少最近生成环境，无法进行 AI 修改");
      return;
    }
    if (!revisionInstruction.trim()) {
      toast.error("请输入修改要求");
      return;
    }
    setRegenerating(true);
    try {
      const run = await createUiAutomationRevisionRun(projectId, assetId, {
        reason_code: "user_requested_change",
        instruction: revisionInstruction.trim(),
        environment_id: latestGeneration.environment_id,
        exploration_run_id: latestGeneration.exploration_run_id || undefined,
        run_after_revision: runAfterRevision,
      });
      setRevisionDialogOpen(false);
      toast.success(`已创建 AI 修改任务 ${run.id}`);
      await loadDetail(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "AI 修改失败");
    } finally {
      setRegenerating(false);
    }
  }

  async function deleteSelectedRuns() {
    const runIds = selectedRunIds.filter((id) => {
      const run = executionRuns.find((item) => item.id === id);
      return run && !ACTIVE_EXECUTION_STATUSES.has(run.status);
    });
    if (runIds.length === 0) {
      toast.error("请先选择已完成的运行记录");
      return;
    }

    setDeletingRuns(true);
    try {
      await Promise.all(runIds.map((runId) => deleteUiAutomationExecutionRun(projectId, runId)));
      setSelectedRunIds([]);
      toast.success(`已删除 ${runIds.length} 条运行记录及对应产物`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "运行记录删除失败");
    } finally {
      await loadDetail(false);
      setDeletingRuns(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("uiAutomation", { label: asset?.source_title || "自动化资产" })}
      projectScope="project"
      title="UI 自动化资产详情"
    >
      <ShellSection className="space-y-6">
        <header className="flex flex-col gap-5 border-b pb-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <h1 className="max-w-4xl text-balance font-semibold text-lg tracking-tight sm:text-xl">
              {asset?.source_title || "UI 自动化资产"}
            </h1>
          </div>
          <div className="grid grid-cols-3 gap-2 lg:flex lg:flex-nowrap lg:justify-end">
            <Button asChild variant="outline">
              <Link href="/automation/ui">
                <ArrowLeft className="size-4" />
                返回列表
              </Link>
            </Button>
            <Button disabled={regenerating || !asset} onClick={openRevisionDialog} variant="outline">
              {regenerating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              AI 修改
            </Button>
            <Button disabled={!canExecute} onClick={() => void execute()}>
              {executeLoading ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              执行测试
            </Button>
          </div>
        </header>

        {loading && !asset ? <LoadingState /> : null}

        {asset ? (
          <Tabs onValueChange={setActiveTab} value={activeTab}>
            <TabsList variant="line">
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="runs">执行</TabsTrigger>
            </TabsList>

            <TabsContent className="space-y-6 pt-5" value="overview">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.85fr)]">
                <section className="border bg-card p-5">
                  <SectionEyebrow icon={Workflow} label="生命周期" />
                  <div className="mt-6 grid grid-cols-3 gap-2 sm:gap-4">
                    {generationStages.map((stage, index) => {
                      const state = stageState(stage.key, latestGeneration, latestExecution, asset.status);
                      return (
                        <div className="relative" key={stage.key}>
                          {index < generationStages.length - 1 ? (
                            <div
                              className={`absolute top-4 left-[calc(50%+1.25rem)] h-px w-[calc(100%-2.5rem)] ${state === "done" ? "bg-emerald-500/60" : "bg-border"}`}
                            />
                          ) : null}
                          <div className="relative flex flex-col items-center text-center">
                            <span
                              className={`grid size-8 place-items-center rounded-full border ${state === "done" ? "border-emerald-500/50 bg-emerald-500/12 text-emerald-500" : state === "error" ? "border-red-500/50 bg-red-500/12 text-red-400" : "border-border bg-muted text-muted-foreground"}`}
                            >
                              {state === "done" ? (
                                <CheckCircle2 className="size-4" />
                              ) : state === "error" ? (
                                <XCircle className="size-4" />
                              ) : (
                                <stage.icon className="size-4" />
                              )}
                            </span>
                            <span className="mt-3 font-medium text-xs">{stage.label}</span>
                            <span className="mt-1 text-[11px] text-muted-foreground">{stateLabel(state)}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>

                <EnvironmentPanel
                  environmentId={executionEnvironmentId}
                  environments={environments}
                  loading={loading}
                  onEnvironmentChange={setExecutionEnvironmentId}
                />
              </div>

              <section className="border bg-card p-5">
                <SectionEyebrow icon={ShieldCheck} label="来源与准入" />
                <div className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
                  <DetailValue label="源测试用例" mono value={asset.test_case_id} />
                  <DetailValue label="源版本" value={`v${asset.source_version}`} />
                  <DetailValue label="探索任务" mono value={latestGeneration?.exploration_run_id || "未绑定"} />
                  <DetailValue label="更新时间" value={formatDateTime(asset.updated_at)} />
                </div>
                <div className="mt-6 grid gap-3 border-t pt-5 sm:grid-cols-3">
                  <HealthItem
                    icon={ShieldCheck}
                    label="Locator 健康度"
                    value={locatorRequired ? `${locatorAvailable} 个已通过 / 共 ${locatorRequired} 个` : "暂无统计"}
                    tone={locatorReady ? "good" : "warn"}
                  />
                  <HealthItem icon={Code2} label="测试代码" value="已生成，可审计" tone="good" />
                  <HealthItem
                    icon={Clock3}
                    label="最近生成"
                    value={latestGeneration ? formatDateTime(latestGeneration.created_at) : "暂无记录"}
                    tone="neutral"
                  />
                </div>
              </section>

              <section>
                <SectionEyebrow icon={FileText} label="生成记录" />
                <div className="mt-3 overflow-hidden border">
                  <GenerationTable runs={generationRuns} />
                </div>
                {latestGeneration?.error_message ? <ErrorCallout message={latestGeneration.error_message} /> : null}
              </section>

              <section>
                <SectionEyebrow icon={TerminalSquare} label="生成文件" />
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <PathValue icon={Code2} label="测试代码" value={asset.test_file_path} />
                  <PathValue icon={Database} label="测试数据" value={asset.data_file_path} />
                  <PathValue icon={FileJson} label="AutomationPlan" value={asset.plan_file_path} />
                  <PathValue icon={TerminalSquare} label="Pytest Node ID" value={asset.pytest_node_id} />
                </div>
              </section>
            </TabsContent>

            <TabsContent className="space-y-5 pt-5" value="runs">
              <div className="grid gap-3 sm:grid-cols-4">
                <StatBlock label="总运行" value={String(stats.total)} />
                <StatBlock label="通过" value={String(stats.passed)} tone="good" />
                <StatBlock label="失败" value={String(stats.failed)} tone="bad" />
                <StatBlock
                  label="通过率"
                  value={stats.total ? `${Math.round((stats.passed / stats.total) * 100)}%` : "-"}
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Button
                  className="border-red-200 bg-red-50 text-red-700 hover:border-red-300 hover:bg-red-100 hover:text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
                  disabled={deletingRuns || selectedRunIds.length === 0}
                  onClick={() => setDeleteConfirmOpen(true)}
                  variant="outline"
                >
                  {deletingRuns ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                  删除{selectedRunIds.length > 0 ? ` (${selectedRunIds.length})` : ""}
                </Button>
                <Button disabled={!canExecute} onClick={() => void execute()}>
                  {executeLoading ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
                  执行测试
                </Button>
              </div>
              <div className="overflow-hidden border">
                <ExecutionTable
                  assetId={assetId}
                  deleting={deletingRuns}
                  onSelectionChange={setSelectedRunIds}
                  projectId={projectId}
                  runs={executionRuns}
                  selectedRunIds={selectedRunIds}
                />
              </div>
            </TabsContent>
          </Tabs>
        ) : null}
      </ShellSection>
      <Dialog
        onOpenChange={(open) => {
          if (!regenerating) setRevisionDialogOpen(open);
        }}
        open={revisionDialogOpen}
      >
        <DialogContent
          aria-describedby={undefined}
          className="grid gap-0 overflow-hidden p-0 sm:max-w-lg [&>[data-slot=dialog-close]]:top-4 [&>[data-slot=dialog-close]]:right-4"
        >
          <DialogHeader className="border-b bg-muted/20 px-6 py-5 pr-14">
            <div className="flex items-center gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-primary/20 bg-primary/10 text-primary shadow-xs">
                <Sparkles className="size-[18px]" />
              </span>
              <DialogTitle className="font-semibold text-lg leading-6">AI 修改自动化脚本</DialogTitle>
            </div>
          </DialogHeader>
          <div className="space-y-5 px-6 py-6">
            <Field className="gap-2.5">
              <div className="flex items-center justify-between gap-4">
                <FieldLabel className="font-semibold" htmlFor="ui-automation-revision-instruction">
                  修改要求
                </FieldLabel>
                <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
                  {revisionInstruction.length}/2000
                </span>
              </div>
              <Textarea
                autoFocus
                className="min-h-36 resize-none bg-muted/15 px-4 py-3.5 text-sm leading-6 shadow-[inset_0_1px_2px_rgba(15,23,42,0.035)] placeholder:text-muted-foreground/75 focus-visible:bg-background"
                id="ui-automation-revision-instruction"
                maxLength={2000}
                onChange={(event) => setRevisionInstruction(event.target.value)}
                placeholder="告诉 AI 需要怎样修改脚本"
                value={revisionInstruction}
              />
            </Field>
            <label
              className="group flex cursor-pointer items-center gap-3 rounded-lg border border-border/70 bg-muted/20 px-4 py-3.5 text-sm transition-colors hover:border-primary/20 hover:bg-primary/[0.035]"
              htmlFor="ui-automation-run-after-revision"
            >
              <Checkbox
                checked={runAfterRevision}
                className="size-[18px]"
                id="ui-automation-run-after-revision"
                onCheckedChange={(checked) => setRunAfterRevision(Boolean(checked))}
              />
              <span className="font-medium">修改完成后运行测试</span>
            </label>
          </div>
          <DialogFooter className="mx-0 mb-0 rounded-none bg-muted/25 px-6 py-4">
            <Button
              className="min-w-20"
              disabled={regenerating}
              onClick={() => setRevisionDialogOpen(false)}
              variant="outline"
            >
              取消
            </Button>
            <Button
              className="min-w-28 shadow-xs"
              disabled={regenerating || !revisionInstruction.trim()}
              onClick={() => void submitRevision()}
            >
              {regenerating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              开始修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog onOpenChange={setDeleteConfirmOpen} open={deleteConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除选中的运行记录</AlertDialogTitle>
            <AlertDialogDescription>
              将删除 {selectedRunIds.length} 条运行记录，以及对应的日志和截图产物。此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingRuns}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deletingRuns}
              onClick={() => void deleteSelectedRuns()}
            >
              删除记录和产物
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </PageShell>
  );
}

function statusLabel(status: string) {
  return statusLabels[status] ?? status;
}

function stageState(
  key: string,
  generation: UiAutomationGenerationRun | null,
  execution: UiAutomationExecutionRun | null,
  assetStatus: string,
) {
  if (key === "queued") return generation?.status === "failed" ? "error" : generation?.status ? "done" : "pending";
  if (key === "completed")
    return assetStatus === "degraded" || generation?.status === "failed"
      ? "error"
      : generation?.status === "completed"
        ? "done"
        : "pending";
  return execution?.status === "failed"
    ? "error"
    : execution?.status === "passed"
      ? "done"
      : execution?.status === "running"
        ? "active"
        : "pending";
}

function stateLabel(state: string) {
  return state === "done" ? "已完成" : state === "error" ? "需处理" : state === "active" ? "执行中" : "待开始";
}

function LoadingState() {
  return (
    <div className="flex min-h-64 items-center justify-center text-muted-foreground text-sm">
      <Loader2 className="mr-2 size-4 animate-spin" />
      资产详情加载中
    </div>
  );
}

function SectionEyebrow({ icon: Icon, label }: { icon: typeof Workflow; label: string }) {
  return (
    <div className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground uppercase tracking-[0.14em]">
      <Icon className="size-3.5" />
      {label}
    </div>
  );
}

function MiniMetric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className={`mt-1 truncate text-sm ${mono ? "font-mono text-xs" : "font-medium"}`} title={value}>
        {value}
      </div>
    </div>
  );
}

function DetailValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <MiniMetric label={label} mono={mono} value={value} />;
}

function HealthItem({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof ShieldCheck;
  label: string;
  value: string;
  tone: "good" | "warn" | "neutral";
}) {
  const color = tone === "good" ? "text-emerald-500" : tone === "warn" ? "text-amber-500" : "text-muted-foreground";
  return (
    <div className="flex min-w-0 items-start gap-3">
      <Icon className={`mt-0.5 size-4 shrink-0 ${color}`} />
      <div className="min-w-0">
        <div className="text-muted-foreground text-xs">{label}</div>
        <div className="mt-1 truncate font-medium text-sm" title={value}>
          {value}
        </div>
      </div>
    </div>
  );
}

function ErrorCallout({ message }: { message: string }) {
  return (
    <div className="mt-4 border-red-500 border-l-2 bg-red-500/8 px-3 py-2 text-red-700 text-xs dark:text-red-300">
      <div className="mb-1 font-medium">需要处理</div>
      <p className="whitespace-pre-wrap">{message}</p>
    </div>
  );
}

function GenerationTable({ runs }: { runs: UiAutomationGenerationRun[] }) {
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b bg-muted/30 text-muted-foreground text-xs">
        <tr>
          <th className="px-4 py-3 font-medium">生成任务</th>
          <th className="px-4 py-3 font-medium">状态</th>
          <th className="px-4 py-3 font-medium">创建时间</th>
          <th className="px-4 py-3 text-right font-medium">变更文件</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr className="border-b last:border-0" key={run.id}>
            <td className="max-w-56 truncate px-4 py-3 font-mono text-xs" title={run.id}>
              {run.id}
            </td>
            <td className="px-4 py-3">
              <StatusBadge tone={chineseCompletionTone(run.status)}>{statusLabel(run.status)}</StatusBadge>
            </td>
            <td className="px-4 py-3 text-muted-foreground text-xs">{formatDateTime(run.created_at)}</td>
            <td className="px-4 py-3 text-right font-mono text-xs">{run.changed_files.length}</td>
          </tr>
        ))}
        {runs.length === 0 ? (
          <tr>
            <td className="h-20 px-4 text-center text-muted-foreground text-xs" colSpan={4}>
              暂无生成记录
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

function ExecutionTable({
  runs,
  projectId,
  assetId,
  selectedRunIds,
  deleting,
  onSelectionChange,
}: {
  runs: UiAutomationExecutionRun[];
  projectId: string;
  assetId: string;
  selectedRunIds: string[];
  deleting: boolean;
  onSelectionChange: (ids: string[]) => void;
}) {
  const deletableRuns = runs.filter((run) => !ACTIVE_EXECUTION_STATUSES.has(run.status));
  const allSelected = deletableRuns.length > 0 && deletableRuns.every((run) => selectedRunIds.includes(run.id));
  const partiallySelected = !allSelected && deletableRuns.some((run) => selectedRunIds.includes(run.id));

  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b bg-muted/30 text-muted-foreground text-xs">
        <tr>
          <th className="w-10 px-4 py-3 font-medium">
            <Checkbox
              aria-label="选择全部已完成的运行记录"
              checked={allSelected ? true : partiallySelected ? "indeterminate" : false}
              disabled={deleting || deletableRuns.length === 0}
              onCheckedChange={(checked) => onSelectionChange(checked ? deletableRuns.map((run) => run.id) : [])}
            />
          </th>
          <th className="px-4 py-3 font-medium">运行</th>
          <th className="px-4 py-3 font-medium">环境</th>
          <th className="px-4 py-3 font-medium">状态</th>
          <th className="px-4 py-3 font-medium">开始时间</th>
          <th className="px-4 py-3 text-right font-medium">证据</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr
            className="border-b last:border-0"
            data-state={selectedRunIds.includes(run.id) ? "selected" : undefined}
            key={run.id}
          >
            <td className="px-4 py-3">
              <Checkbox
                aria-label={`选择运行记录 ${run.id}`}
                checked={selectedRunIds.includes(run.id)}
                disabled={deleting || ACTIVE_EXECUTION_STATUSES.has(run.status)}
                onCheckedChange={(checked) =>
                  onSelectionChange(
                    checked ? [...new Set([...selectedRunIds, run.id])] : selectedRunIds.filter((id) => id !== run.id),
                  )
                }
              />
            </td>
            <td className="px-4 py-3">
              <Link
                className="font-mono text-primary text-xs hover:underline"
                href={`/projects/${projectId}/automation/ui/assets/${assetId}/runs/${run.id}`}
              >
                {run.id}
              </Link>
            </td>
            <td className="max-w-44 truncate px-4 py-3 font-mono text-xs" title={run.environment_id}>
              {run.environment_id}
            </td>
            <td className="px-4 py-3">
              <StatusBadge tone={chineseCompletionTone(run.status)}>{statusLabel(run.status)}</StatusBadge>
            </td>
            <td className="px-4 py-3 text-muted-foreground text-xs">
              {formatDateTime(run.started_at || run.created_at)}
            </td>
            <td className="px-4 py-3 text-right font-mono text-xs">{run.screenshot_paths.length}</td>
          </tr>
        ))}
        {runs.length === 0 ? (
          <tr>
            <td className="h-24 px-4 text-center text-muted-foreground text-xs" colSpan={6}>
              这条自动化资产还没有运行记录。选择运行环境后开始第一次执行。
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

function StatBlock({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "good" | "bad" | "neutral";
}) {
  const color = tone === "good" ? "text-emerald-500" : tone === "bad" ? "text-red-400" : "text-foreground";
  return (
    <div className="border bg-card px-4 py-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={`mt-2 font-semibold text-2xl ${color}`}>{value}</div>
    </div>
  );
}

function PathValue({ icon: Icon, label, value }: { icon: typeof Code2; label: string; value: string }) {
  return (
    <div className="min-w-0 border bg-card p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-2 break-all font-mono text-xs leading-relaxed">{value || "-"}</div>
    </div>
  );
}
