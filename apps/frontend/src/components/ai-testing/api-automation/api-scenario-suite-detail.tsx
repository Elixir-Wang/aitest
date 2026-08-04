"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Globe2,
  Layers3,
  Loader2,
  Pencil,
  Play,
  RotateCw,
  Server,
  Sparkles,
} from "lucide-react";

import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { StatusBadge, type StatusBadgeTone } from "@/components/ui/status-badge";
import {
  type ApiAutomationBatchRun,
  type ApiAutomationEnvironment,
  type ApiAutomationScenario,
  type ApiAutomationScenarioSuite,
  formatDateTime,
  getApiAutomationScenarioSuite,
  listApiAutomationEnvironments,
  listApiAutomationScenarios,
  runApiAutomationScenarioSuite,
  updateApiAutomationScenarioSuite,
} from "@/lib/api-client";
import { toast } from "@/lib/toast";

import { ApiScenarioSuiteDialog } from "./api-scenario-suite-dialog";

type ApiScenarioSuiteDetailProps = {
  projectId: string;
  suiteId: string;
};

export function ApiScenarioSuiteDetail({ projectId, suiteId }: ApiScenarioSuiteDetailProps) {
  const [suite, setSuite] = useState<ApiAutomationScenarioSuite | null>(null);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [scenarios, setScenarios] = useState<ApiAutomationScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [running, setRunning] = useState(false);
  const [savingEnvironment, setSavingEnvironment] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const loadData = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const [suiteRow, environmentRows, scenarioRows] = await Promise.all([
          getApiAutomationScenarioSuite(projectId, suiteId),
          listApiAutomationEnvironments(projectId),
          listApiAutomationScenarios(projectId),
        ]);
        setSuite(suiteRow);
        setEnvironments(environmentRows);
        setScenarios(scenarioRows);
        setLoadError("");
      } catch (error) {
        if (!silent) setLoadError(error instanceof Error ? error.message : "测试集加载失败");
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [projectId, suiteId],
  );

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (suite?.latest_batch?.status !== "queued" && suite?.latest_batch?.status !== "running") return;
    const timer = window.setInterval(() => void loadData(true), 2000);
    return () => window.clearInterval(timer);
  }, [loadData, suite?.latest_batch?.status]);

  async function runSuite() {
    if (!suite) return;
    setRunning(true);
    try {
      const batch = await runApiAutomationScenarioSuite(projectId, suite.id);
      toast.success(`“${suite.name}”已开始运行，共 ${batch.counts.total} 个场景`);
      await loadData(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "测试集启动失败");
    } finally {
      setRunning(false);
    }
  }

  async function changeEnvironment(environmentId: string) {
    if (!suite || environmentId === suite.api_environment_id) return;

    const previousSuite = suite;
    const environment = environments.find((item) => item.id === environmentId) ?? null;
    setSavingEnvironment(true);
    setSuite({
      ...suite,
      api_environment_id: environmentId,
      environment: environment
        ? { id: environment.id, name: environment.name, api_base_url: environment.api_base_url }
        : null,
    });

    try {
      const savedSuite = await updateApiAutomationScenarioSuite(projectId, suite.id, {
        name: suite.name,
        description: suite.description,
        api_environment_id: environmentId,
        scenario_ids: suite.scenarios.map((scenario) => scenario.id),
      });
      setSuite(savedSuite);
    } catch (error) {
      setSuite(previousSuite);
      toast.error(error instanceof Error ? error.message : "运行环境保存失败");
    } finally {
      setSavingEnvironment(false);
    }
  }

  if (loading) return <SuiteDetailSkeleton />;

  if (loadError || !suite) {
    return (
      <div className="grid min-h-[360px] place-items-center border-y bg-card px-6 text-center">
        <div>
          <CircleAlert className="mx-auto size-8 text-destructive" />
          <p className="mt-3 font-semibold">无法打开测试集</p>
          <p className="mt-1 text-muted-foreground text-sm">{loadError || "测试集不存在或已被删除"}</p>
          <Button asChild className="mt-5" variant="outline">
            <Link href={`/projects/${projectId}/automation/api?tab=batch-runs`}>返回批量运行</Link>
          </Button>
        </div>
      </div>
    );
  }

  const latestBatch = suite.latest_batch;
  const runnable = suite.scenarios.length > 0 && suite.scenarios.every(isRunnableSuiteScenario);
  const enabledSteps = suite.scenarios.reduce((sum, scenario) => sum + scenario.enabled_step_count, 0);
  const isActive = latestBatch?.status === "queued" || latestBatch?.status === "running";

  return (
    <>
      <main className="overflow-hidden rounded-lg border border-border/80 bg-card shadow-[0_24px_70px_color-mix(in_srgb,var(--primary),transparent_94%)]">
        <header className="relative px-5 py-7 sm:px-8 sm:py-9">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-primary/60" />
          <div className="grid gap-7 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="break-words font-semibold text-3xl leading-tight tracking-normal sm:text-[2rem]">
                  {suite.name}
                </h1>
                <StatusBadge className="h-6 rounded-md px-2" tone={latestBatch ? batchTone(latestBatch) : "neutral"}>
                  <span className="mr-1.5 size-1.5 rounded-full bg-current" />
                  {latestBatch ? batchLabel(latestBatch) : "尚未运行"}
                </StatusBadge>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => setEditOpen(true)} size="lg" variant="outline">
                <Pencil />
                编辑
              </Button>
              <Button
                className="min-w-32 shadow-[0_10px_28px_color-mix(in_srgb,var(--primary),transparent_76%)]"
                disabled={running || !runnable || isActive}
                onClick={runSuite}
                size="lg"
              >
                {running || isActive ? <Loader2 className="animate-spin" /> : <Play />}
                {isActive ? "运行中" : "运行测试集"}
              </Button>
            </div>
          </div>

          <div className="mt-7 grid overflow-hidden rounded-md border border-border/70 bg-muted/25 sm:grid-cols-2 xl:grid-cols-4">
            <EnvironmentOverview
              disabled={savingEnvironment}
              environments={environments}
              onChange={changeEnvironment}
              suite={suite}
            />
            <OverviewItem
              helper="按顺序串行执行"
              icon={Layers3}
              label="场景范围"
              value={`${suite.scenarios.length} 个场景`}
            />
            <OverviewItem helper="仅统计已启用步骤" icon={Sparkles} label="执行步骤" value={`${enabledSteps} 个步骤`} />
            <OverviewItem
              helper={`创建于 ${formatDateTime(suite.created_at)}`}
              icon={Clock3}
              label="最后更新"
              value={formatDateTime(suite.updated_at)}
            />
          </div>

          {!runnable ? (
            <div className="mt-4 flex items-start gap-2.5 rounded-md border border-amber-300/60 bg-amber-50 px-3.5 py-3 text-amber-950 dark:border-amber-800/60 dark:bg-amber-950/20 dark:text-amber-100">
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
              <p className="text-sm leading-5">
                当前测试集暂不可运行。请为每个场景保存至少一个启用步骤，或在编辑测试集中移除未就绪场景。
              </p>
            </div>
          ) : null}
        </header>

        <div className="grid border-border/80 border-t xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="min-w-0 px-5 py-7 sm:px-8 sm:py-9">
            <h2 className="font-semibold text-xl">执行计划</h2>

            {suite.scenarios.length > 0 ? (
              <ol className="mt-5 border-border/70 border-t">
                {suite.scenarios.map((scenario, index) => (
                  <ScenarioRow
                    index={index}
                    key={scenario.id}
                    projectId={projectId}
                    scenario={scenario}
                    total={suite.scenarios.length}
                  />
                ))}
              </ol>
            ) : (
              <div className="mt-7 border-y border-dashed py-12 text-center">
                <Layers3 className="mx-auto size-6 text-muted-foreground" />
                <p className="mt-3 font-medium text-sm">测试集还没有场景</p>
                <p className="mt-1 text-muted-foreground text-xs">编辑测试集并加入至少一个可运行场景。</p>
                <Button className="mt-4" onClick={() => setEditOpen(true)} size="sm" variant="outline">
                  <Pencil />
                  编辑测试集
                </Button>
              </div>
            )}
          </section>

          <LatestRunPanel batch={latestBatch} />
        </div>
      </main>

      <ApiScenarioSuiteDialog
        environments={environments}
        onOpenChange={setEditOpen}
        onSaved={(savedSuite) => setSuite(savedSuite)}
        open={editOpen}
        projectId={projectId}
        scenarios={scenarios}
        suite={suite}
      />
    </>
  );
}

function SuiteDetailSkeleton() {
  return (
    <div aria-label="测试集加载中" className="animate-pulse overflow-hidden rounded-lg border bg-card" role="status">
      <div className="px-5 py-8 sm:px-8">
        <div className="h-3 w-28 rounded bg-muted" />
        <div className="mt-7 h-8 w-64 max-w-full rounded bg-muted" />
        <div className="mt-4 h-4 w-[34rem] max-w-full rounded bg-muted/70" />
        <div className="mt-8 grid gap-px overflow-hidden rounded-md bg-border sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div className="h-24 bg-muted/40" key={item} />
          ))}
        </div>
      </div>
      <div className="grid border-t xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4 p-8">
          <div className="h-6 w-36 rounded bg-muted" />
          <div className="h-24 rounded bg-muted/50" />
          <div className="h-24 rounded bg-muted/50" />
        </div>
        <div className="h-80 border-l bg-muted/25" />
      </div>
    </div>
  );
}

function OverviewItem({
  helper,
  icon: Icon,
  label,
  value,
}: {
  helper: string;
  icon: typeof Server;
  label: string;
  value: string;
}) {
  return (
    <div className="group flex min-w-0 items-start gap-3 border-border/70 border-b px-4 py-4 last:border-b-0 sm:nth-last-2:border-b-0 sm:odd:border-r xl:border-r xl:border-b-0 xl:last:border-r-0">
      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-background text-primary ring-1 ring-border/70 transition-colors group-hover:bg-primary/8">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0">
        <p className="text-muted-foreground text-xs">{label}</p>
        <p className="mt-0.5 truncate font-semibold text-sm" title={value}>
          {value}
        </p>
        <p className="mt-0.5 truncate text-[11px] text-muted-foreground" title={helper}>
          {helper}
        </p>
      </div>
    </div>
  );
}

function EnvironmentOverview({
  disabled,
  environments,
  onChange,
  suite,
}: {
  disabled: boolean;
  environments: ApiAutomationEnvironment[];
  onChange: (environmentId: string) => void;
  suite: ApiAutomationScenarioSuite;
}) {
  return (
    <div className="group flex min-w-0 items-start gap-3 border-border/70 border-b px-4 py-4 last:border-b-0 sm:nth-last-2:border-b-0 sm:odd:border-r xl:border-r xl:border-b-0 xl:last:border-r-0">
      <span className="grid size-8 shrink-0 place-items-center rounded-md bg-background text-primary ring-1 ring-border/70 transition-colors group-hover:bg-primary/8">
        <Server className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-muted-foreground text-xs">运行环境</p>
        <Select
          aria-label="切换运行环境"
          className="mt-1 h-7 min-w-0 border-0 bg-transparent px-0 font-semibold shadow-none hover:bg-transparent dark:bg-transparent dark:hover:bg-transparent"
          disabled={disabled || environments.length === 0}
          placeholder="请选择运行环境"
          setValue={onChange}
          value={suite.api_environment_id}
        >
          {environments.map((environment) => (
            <SelectOption key={environment.id} value={environment.id}>
              {environment.name}
            </SelectOption>
          ))}
        </Select>
        <p className="mt-0.5 truncate text-[11px] text-muted-foreground" title={suite.environment?.api_base_url}>
          {disabled ? "自动保存中" : suite.environment?.api_base_url || "环境地址不可用"}
        </p>
      </div>
    </div>
  );
}

function ScenarioRow({
  scenario,
  projectId,
  index,
  total,
}: {
  scenario: ApiAutomationScenarioSuite["scenarios"][number];
  projectId: string;
  index: number;
  total: number;
}) {
  const runnable = isRunnableSuiteScenario(scenario);

  return (
    <li className="group relative grid grid-cols-[44px_minmax(0,1fr)] items-center gap-4 border-border/70 border-b py-4 transition-colors hover:bg-muted/25 sm:grid-cols-[52px_minmax(0,1fr)] sm:px-2">
      {index < total - 1 ? (
        <span className="absolute top-[3.8rem] bottom-[-1.3rem] left-[21px] w-px bg-primary/25 sm:left-[27px]" />
      ) : null}
      <span className="relative z-10 grid size-9 place-items-center rounded-md border border-primary/25 bg-primary/[0.06] font-mono font-semibold text-primary text-xs tabular-nums shadow-[0_0_0_4px_var(--card)]">
        {String(index + 1).padStart(2, "0")}
      </span>

      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Link
            className="min-w-0 truncate rounded-sm font-semibold text-sm outline-none transition-colors hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
            href={`/projects/${projectId}/automation/api/scenarios/${scenario.id}`}
          >
            {scenario.name}
          </Link>
          <StatusBadge className="h-5 rounded px-1.5 text-[10px]" tone={runnable ? "success" : "warning"}>
            {runnable ? "已就绪" : "需处理"}
          </StatusBadge>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 text-[11px] text-muted-foreground">
          <span>{scenario.enabled_step_count} 个启用步骤</span>
          <span>修订 v{scenario.revision}</span>
          <Link
            aria-label={`打开场景“${scenario.name}”`}
            className="-ml-1 inline-flex size-6 items-center justify-center rounded-sm outline-none transition-colors hover:bg-muted hover:text-primary focus-visible:ring-2 focus-visible:ring-ring"
            href={`/projects/${projectId}/automation/api/scenarios/${scenario.id}`}
          >
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </li>
  );
}

function LatestRunPanel({ batch }: { batch: ApiAutomationBatchRun | null }) {
  if (!batch) {
    return (
      <aside className="border-border/80 border-t bg-muted/20 px-5 py-7 sm:px-8 sm:py-9 xl:border-t-0 xl:border-l">
        <p className="font-medium text-primary text-xs">运行洞察</p>
        <h2 className="mt-1.5 font-semibold text-xl">最近运行</h2>
        <div className="mt-8 border-y border-dashed py-10 text-center">
          <Play className="mx-auto size-6 text-muted-foreground" />
          <p className="mt-3 font-medium text-sm">等待首次运行</p>
          <p className="mx-auto mt-1 max-w-56 text-muted-foreground text-xs leading-5">
            运行后，这里会显示通过率、结果分布、耗时和报告入口。
          </p>
        </div>
      </aside>
    );
  }

  const completed = batch.status === "completed";
  const passRate = batch.counts.total > 0 ? Math.round((batch.counts.passed / batch.counts.total) * 100) : 0;
  const duration = formatRunDuration(batch.started_at, batch.finished_at);
  const statusIcon =
    batch.result === "passed"
      ? CheckCircle2
      : batch.status === "queued" || batch.status === "running"
        ? Loader2
        : CircleAlert;
  const StatusIcon = statusIcon;

  return (
    <aside className="border-border/80 border-t bg-muted/20 px-5 py-7 sm:px-8 sm:py-9 xl:border-t-0 xl:border-l">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-medium text-primary text-xs">运行洞察</p>
          <h2 className="mt-1.5 font-semibold text-xl">最近运行</h2>
        </div>
        <StatusBadge className="h-6 rounded-md" tone={batchTone(batch)}>
          {batchLabel(batch)}
        </StatusBadge>
      </div>

      <div className="mt-7 flex items-end justify-between gap-4 border-border/80 border-b pb-6">
        <div>
          <p className="text-muted-foreground text-xs">场景通过率</p>
          <p className="mt-1 font-mono font-semibold text-4xl tabular-nums leading-none">
            {completed ? passRate : "--"}
            {completed ? <span className="ml-1 text-base text-muted-foreground">%</span> : null}
          </p>
        </div>
        <span className="grid size-11 place-items-center rounded-md border bg-background">
          <StatusIcon
            className={`size-5 ${batch.status === "queued" || batch.status === "running" ? "animate-spin text-primary" : batch.result === "passed" ? "text-emerald-600" : "text-amber-600"}`}
          />
        </span>
      </div>

      {completed ? <ResultDistribution batch={batch} /> : null}

      <dl className="mt-6 space-y-3 text-xs">
        <RunDetail icon={Globe2} label="运行环境" value={batch.environment?.name || "环境已删除"} />
        <RunDetail icon={Clock3} label="开始时间" value={formatDateTime(batch.started_at || batch.created_at)} />
        <RunDetail icon={RotateCw} label="运行耗时" value={duration} />
      </dl>

      {batch.error_message ? (
        <div className="mt-5 rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2.5 text-destructive text-xs leading-5">
          {batch.error_message}
        </div>
      ) : null}

      {completed ? (
        <Button asChild className="mt-7 w-full" size="lg" variant="outline">
          <Link href={`/reports/api/${batch.id}`}>
            查看完整报告
            <ArrowUpRight />
          </Link>
        </Button>
      ) : (
        <div className="mt-7 flex items-center gap-2 border-t pt-5 text-muted-foreground text-xs">
          <Loader2 className="size-3.5 animate-spin text-primary" />
          页面会自动刷新运行结果
        </div>
      )}
    </aside>
  );
}

function ResultDistribution({ batch }: { batch: ApiAutomationBatchRun }) {
  const items = [
    { label: "通过", value: batch.counts.passed, color: "bg-emerald-500" },
    { label: "待确认", value: batch.counts.observed, color: "bg-amber-400" },
    { label: "失败", value: batch.counts.failed, color: "bg-rose-500" },
    { label: "异常", value: batch.counts.error, color: "bg-slate-500" },
  ];

  return (
    <div className="mt-6">
      <div aria-label="运行结果分布" className="flex h-1.5 overflow-hidden rounded-sm bg-border/60" role="img">
        {items.map((item) =>
          item.value > 0 ? (
            <span
              className={item.color}
              key={item.label}
              style={{ width: `${(item.value / Math.max(batch.counts.total, 1)) * 100}%` }}
            />
          ) : null,
        )}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3">
        {items.map((item) => (
          <div className="flex items-center justify-between gap-3 text-xs" key={item.label}>
            <span className="flex items-center gap-2 text-muted-foreground">
              <span className={`size-1.5 rounded-full ${item.color}`} />
              {item.label}
            </span>
            <span className="font-mono font-semibold tabular-nums">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RunDetail({ icon: Icon, label, value }: { icon: typeof Clock3; label: string; value: string }) {
  return (
    <div className="grid grid-cols-[16px_64px_minmax(0,1fr)] items-center gap-2">
      <Icon className="size-3.5 text-muted-foreground" />
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate text-right font-medium" title={value}>
        {value}
      </dd>
    </div>
  );
}

function formatRunDuration(startedAt: string | null, finishedAt: string | null) {
  if (!startedAt) return "尚未开始";
  if (!finishedAt) return "运行中";
  const durationSeconds = Math.max(0, Math.round((Date.parse(finishedAt) - Date.parse(startedAt)) / 1000));
  if (durationSeconds < 60) return `${durationSeconds} 秒`;
  const minutes = Math.floor(durationSeconds / 60);
  const seconds = durationSeconds % 60;
  if (minutes < 60) return `${minutes} 分 ${seconds} 秒`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分`;
}

function isRunnableSuiteScenario(scenario: ApiAutomationScenarioSuite["scenarios"][number]) {
  return scenario.revision > 0 && scenario.enabled_step_count > 0;
}

function batchLabel(batch: ApiAutomationBatchRun) {
  if (batch.status === "queued") return "排队中";
  if (batch.status === "running") return "运行中";
  if (batch.status === "failed") return "启动失败";
  if (batch.result === "passed") return "全部通过";
  if (batch.result === "observed") return "存在待确认";
  if (batch.result === "failed") return "存在失败";
  if (batch.result === "error") return "运行异常";
  return "已完成";
}

function batchTone(batch: ApiAutomationBatchRun): StatusBadgeTone {
  if (batch.status === "queued" || batch.status === "running") return "processing";
  if (batch.status === "failed" || batch.result === "failed" || batch.result === "error") return "destructive";
  if (batch.result === "observed") return "warning";
  return "success";
}
