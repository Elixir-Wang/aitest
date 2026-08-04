"use client";

import { type CSSProperties, type UIEvent, useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  Clock3,
  ImageIcon,
  Loader2,
  MonitorPlay,
  Play,
  Radio,
  RefreshCw,
  Search,
  Square,
  XCircle,
} from "lucide-react";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import {
  API_BASE_URL,
  apiBlobRequest,
  apiRequest,
  createUiAutomationExecutionRun,
  formatDateTime,
  getUiAutomationExecutionRun,
  getUiAutomationLiveView,
  getUiAutomationRunDetail,
  getUiAutomationRunLogs,
  stopUiAutomationExecutionRun,
  type UiAutomationExecutionRun,
  type UiAutomationIterationResult,
  type UiAutomationLiveView,
  type UiAutomationRunDetail as UiAutomationRunDetailData,
  type UiAutomationStepResult,
} from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";
import { toast } from "@/lib/toast";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const activeStatuses = new Set(["queued", "running", "stopping"]);
const stoppableStatuses = new Set(["queued", "running"]);

export function UiAutomationRunDetail({
  projectId,
  assetId,
  runId,
}: {
  projectId: string;
  assetId: string;
  runId: string;
}) {
  const [run, setRun] = useState<UiAutomationExecutionRun | null>(null);
  const [environmentName, setEnvironmentName] = useState("");
  const [detail, setDetail] = useState<UiAutomationRunDetailData | null>(null);
  const [logs, setLogs] = useState({ stdout: "", stderr: "" });
  const [screenshotUrls, setScreenshotUrls] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [liveViewOpen, setLiveViewOpen] = useState(false);
  const [liveView, setLiveView] = useState<UiAutomationLiveView | null>(null);
  const [liveViewLoading, setLiveViewLoading] = useState(false);
  const [selectedIterationId, setSelectedIterationId] = useState("");
  const [parameterQuery, setParameterQuery] = useState("");
  const [iterationStatus, setIterationStatus] = useState("all");
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [stepArtifactUrls, setStepArtifactUrls] = useState<Record<string, string>>({});

  const loadDetail = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const [nextRun, nextDetail] = await Promise.all([
          getUiAutomationExecutionRun(projectId, runId),
          getUiAutomationRunDetail(projectId, runId),
        ]);
        setRun(nextRun);
        setDetail(nextDetail);
        if (!activeStatuses.has(nextRun.status)) {
          setLogs(await getUiAutomationRunLogs(projectId, runId));
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "UI 自动化运行详情加载失败");
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [projectId, runId],
  );

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (!run?.environment_id) return;
    let disposed = false;
    setEnvironmentName("");
    void apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${projectId}`)
      .then((environments) => {
        if (disposed) return;
        setEnvironmentName(
          environments.find((environment) => environment.id === run.environment_id)?.name ?? "已删除环境",
        );
      })
      .catch(() => {
        if (!disposed) setEnvironmentName("环境信息不可用");
      });
    return () => {
      disposed = true;
    };
  }, [projectId, run?.environment_id]);

  useEffect(() => {
    if (!activeStatuses.has(run?.status ?? "")) return;
    const timer = window.setInterval(() => void loadDetail(false), 2000);
    return () => window.clearInterval(timer);
  }, [loadDetail, run?.status]);

  useEffect(() => {
    if (!run || run.screenshot_paths.length === 0 || activeStatuses.has(run.status)) return;
    let disposed = false;
    const urls: string[] = [];
    void Promise.all(
      run.screenshot_paths.map(async (_, index) => {
        const blob = await apiBlobRequest(
          `/projects/${projectId}/ui-automation/runs/${runId}/artifacts/screenshot?index=${index}`,
        );
        const url = URL.createObjectURL(blob);
        urls.push(url);
        return url;
      }),
    )
      .then((items) => {
        if (disposed) {
          items.forEach((url) => {
            URL.revokeObjectURL(url);
          });
          return;
        }
        setScreenshotUrls(items);
      })
      .catch(() => setScreenshotUrls([]));
    return () => {
      disposed = true;
      urls.forEach((url) => {
        URL.revokeObjectURL(url);
      });
    };
  }, [projectId, run, runId]);

  useEffect(() => {
    if (!liveViewOpen) return;
    let disposed = false;
    let loadingRequest = false;
    const loadLiveView = async () => {
      if (loadingRequest) return;
      loadingRequest = true;
      setLiveViewLoading(true);
      try {
        const nextView = await getUiAutomationLiveView(projectId, runId);
        if (!disposed) setLiveView(nextView);
      } catch (error) {
        if (!disposed) {
          toast.error(error instanceof Error ? error.message : "实时浏览器画面加载失败");
        }
      } finally {
        loadingRequest = false;
        if (!disposed) setLiveViewLoading(false);
      }
    };
    void loadLiveView();
    const timer = window.setInterval(() => void loadLiveView(), 1500);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [liveViewOpen, projectId, runId]);

  const filteredIterations = useMemo(() => {
    const query = parameterQuery.trim().toLowerCase();
    return (detail?.iterations ?? []).filter((iteration) => {
      if (iterationStatus !== "all" && iteration.status !== iterationStatus) return false;
      if (!query) return true;
      return parameterSummary(iteration).toLowerCase().includes(query);
    });
  }, [detail?.iterations, iterationStatus, parameterQuery]);

  const selectedIteration = useMemo(
    () => detail?.iterations.find((iteration) => iteration.iteration_id === selectedIterationId) ?? null,
    [detail?.iterations, selectedIterationId],
  );

  useEffect(() => {
    const iterations = detail?.iterations ?? [];
    if (iterations.length === 0 || iterations.some((item) => item.iteration_id === selectedIterationId)) return;
    const preferred =
      iterations.find((item) => item.status === "running") ??
      iterations.find(
        (item) =>
          item.status === "cancelled" &&
          item.steps.some((step) => step.status === "cancelled" && Boolean(step.started_at)),
      ) ??
      iterations.find((item) => item.status === "failed" || item.status === "infrastructure_error") ??
      iterations[0];
    setSelectedIterationId(preferred.iteration_id);
  }, [detail?.iterations, selectedIterationId]);

  useEffect(() => {
    const artifacts = (selectedIteration?.steps ?? []).flatMap((step) => step.artifacts);
    if (artifacts.length === 0) {
      setStepArtifactUrls({});
      return;
    }
    let disposed = false;
    const urls: string[] = [];
    void Promise.all(
      artifacts.map(async (artifact) => {
        const blob = await apiBlobRequest(
          `/projects/${projectId}/ui-automation/runs/${runId}/step-artifacts/${artifact.artifact_id}`,
        );
        const url = URL.createObjectURL(blob);
        urls.push(url);
        return [artifact.artifact_id, url] as const;
      }),
    )
      .then((entries) => {
        if (!disposed) setStepArtifactUrls(Object.fromEntries(entries));
      })
      .catch(() => {
        if (!disposed) setStepArtifactUrls({});
      });
    return () => {
      disposed = true;
      urls.forEach((url) => {
        URL.revokeObjectURL(url);
      });
    };
  }, [projectId, runId, selectedIteration]);

  useEffect(() => {
    const failedStepId = selectedIteration?.failed_step_id;
    if (!failedStepId) return;
    setExpandedSteps((current) => {
      if (current.has(failedStepId)) return current;
      return new Set([...current, failedStepId]);
    });
  }, [selectedIteration?.failed_step_id]);

  async function rerun() {
    if (!run || activeStatuses.has(run.status)) return;
    setRerunning(true);
    try {
      const created = await createUiAutomationExecutionRun(projectId, assetId, run.environment_id);
      window.location.assign(`/projects/${projectId}/automation/ui/assets/${assetId}/runs/${created.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "重新执行失败");
    } finally {
      setRerunning(false);
    }
  }

  async function stopRun() {
    if (!run || !stoppableStatuses.has(run.status)) return;
    setStopping(true);
    try {
      const updated = await stopUiAutomationExecutionRun(projectId, runId);
      setRun(updated);
      setStopDialogOpen(false);
      toast.success(updated.status === "cancelled" ? "运行已停止" : "已提交停止请求");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "停止运行失败");
      await loadDetail(false);
    } finally {
      setStopping(false);
    }
  }

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "uiAutomation",
        {
          label: "自动化资产",
          href: `/projects/${projectId}/automation/ui/assets/${assetId}?tab=runs`,
        },
        { label: "运行详情" },
      )}
      projectScope="project"
      title="UI 自动化运行详情"
    >
      <ShellSection className="space-y-6">
        <div className="flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-semibold text-2xl">运行详情</h1>
              {run ? (
                <StatusBadge tone={chineseCompletionTone(run.status)}>{statusLabel(run.status)}</StatusBadge>
              ) : null}
            </div>
            <p className="mt-2 break-all font-mono text-muted-foreground text-xs">{runId}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href={`/projects/${projectId}/automation/ui/assets/${assetId}?tab=runs`}>
                <ArrowLeft className="size-4" />
                返回执行记录
              </Link>
            </Button>
            <Button disabled={loading} onClick={() => void loadDetail()} variant="outline">
              {loading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              刷新
            </Button>
            {run && activeStatuses.has(run.status) ? (
              <Button
                aria-label="停止本次运行"
                disabled={run.status === "stopping" || stopping}
                onClick={() => setStopDialogOpen(true)}
                variant="destructive"
              >
                {run.status === "stopping" || stopping ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Square className="size-4 fill-current" />
                )}
                {run.status === "stopping" || stopping ? "停止中…" : "停止运行"}
              </Button>
            ) : (
              <Button disabled={!run || rerunning} onClick={() => void rerun()} variant="outline">
                {rerunning ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
                重新执行
              </Button>
            )}
            <Button disabled={!run} onClick={() => setLiveViewOpen(true)} variant="outline">
              <MonitorPlay className="size-4" />
              {activeStatuses.has(run?.status ?? "") ? "实时查看" : "查看运行状态"}
            </Button>
          </div>
        </div>

        {loading && !run ? (
          <div className="flex min-h-64 items-center justify-center text-muted-foreground text-sm">
            <Loader2 className="mr-2 size-4 animate-spin" />
            运行详情加载中
          </div>
        ) : null}

        {run ? (
          <>
            <div className="grid gap-x-6 gap-y-5 border-b pb-5 sm:grid-cols-2 lg:grid-cols-4">
              <DetailValue label="状态" value={statusLabel(run.status)} />
              <DetailValue label="运行环境" value={environmentName || "加载中…"} />
              <DetailValue label="开始时间" value={formatDateTime(run.started_at || run.created_at)} />
              <DetailValue label="完成时间" value={run.finished_at ? formatDateTime(run.finished_at) : "-"} />
              <DetailValue label="退出码" value={String(run.result.exitcode ?? "-")} />
              <DetailValue label="截图" value={String(run.screenshot_paths.length)} />
              <DetailValue label="执行人" mono value={run.created_by} />
              <DetailValue label="运行 ID" mono value={run.id} />
            </div>

            {run.error_message ? (
              <section>
                <SectionTitle title="失败原因" />
                <pre className="overflow-auto whitespace-pre-wrap rounded-md border border-red-200 bg-red-50 p-3 text-red-800 text-xs dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                  {run.error_message}
                </pre>
              </section>
            ) : null}

            <ExecutionResultPanel
              artifactUrls={stepArtifactUrls}
              detail={detail}
              expandedSteps={expandedSteps}
              filteredIterations={filteredIterations}
              iterationStatus={iterationStatus}
              onIterationStatusChange={setIterationStatus}
              onParameterQueryChange={setParameterQuery}
              onSelectIteration={setSelectedIterationId}
              onToggleStep={(stepId) =>
                setExpandedSteps((current) => {
                  const next = new Set(current);
                  if (next.has(stepId)) next.delete(stepId);
                  else next.add(stepId);
                  return next;
                })
              }
              parameterQuery={parameterQuery}
              selectedIteration={selectedIteration}
            />

            <section>
              <SectionTitle title="原始运行日志" />
              <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-md bg-zinc-950 p-4 font-mono text-xs text-zinc-100 leading-5">
                {logs.stdout ||
                  logs.stderr ||
                  (activeStatuses.has(run.status) ? "任务执行中，日志将在完成后显示。" : "暂无运行日志。")}
              </pre>
              {logs.stdout && logs.stderr ? (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer text-muted-foreground">查看 stderr</summary>
                  <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
                    {logs.stderr}
                  </pre>
                </details>
              ) : null}
            </section>

            <section>
              <SectionTitle title="浏览器证据" />
              {screenshotUrls.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {screenshotUrls.map((url, index) => (
                    <figure className="overflow-hidden rounded-md border" key={url}>
                      {/* biome-ignore lint/performance/noImgElement: authenticated blob URLs cannot use next/image optimization. */}
                      <img
                        alt={`失败截图 ${index + 1}`}
                        className="aspect-video w-full bg-muted object-contain"
                        src={url}
                      />
                      <figcaption className="border-t px-3 py-2 text-muted-foreground text-xs">
                        截图 {index + 1}
                      </figcaption>
                    </figure>
                  ))}
                </div>
              ) : (
                <div className="flex min-h-28 items-center justify-center rounded-md border text-muted-foreground text-sm">
                  <ImageIcon className="mr-2 size-4" />
                  暂无截图证据
                </div>
              )}
            </section>
          </>
        ) : null}
      </ShellSection>

      <Dialog
        onOpenChange={(open) => {
          if (!stopping) setStopDialogOpen(open);
        }}
        open={stopDialogOpen}
      >
        <DialogContent showCloseButton={!stopping}>
          <DialogHeader>
            <DialogTitle>停止此次运行？</DialogTitle>
            <DialogDescription>停止后不能继续本次运行，已生成的日志和截图仍会保留。</DialogDescription>
          </DialogHeader>
          <div className="rounded-md border bg-muted/40 px-3 py-2 font-mono text-muted-foreground text-xs">{runId}</div>
          <DialogFooter>
            <Button disabled={stopping} onClick={() => setStopDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={stopping} onClick={() => void stopRun()} type="button" variant="destructive">
              {stopping ? <Loader2 className="size-4 animate-spin" /> : <Square className="size-4 fill-current" />}
              {stopping ? "停止中…" : "停止运行"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={setLiveViewOpen} open={liveViewOpen}>
        <DialogContent className="top-0 left-0 grid h-dvh w-screen max-w-none translate-x-0 translate-y-0 grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden rounded-none bg-zinc-950 p-0 text-zinc-100 sm:max-w-none">
          <DialogHeader className="border-zinc-800 border-b px-5 py-4 pr-14">
            <div className="flex flex-wrap items-center gap-3">
              <DialogTitle className="text-zinc-100">浏览器操作过程</DialogTitle>
              <LiveStatus status={liveView?.status ?? (liveViewLoading ? "starting" : "waiting")} />
              {liveView ? (
                <span className="font-mono text-xs text-zinc-500">
                  {liveView.width} × {liveView.height}
                </span>
              ) : null}
            </div>
            <DialogDescription className="text-zinc-400">
              {liveView?.message ?? "正在连接运行中的浏览器画面。"}
            </DialogDescription>
          </DialogHeader>
          <div className="flex min-h-0 items-center justify-center overflow-hidden bg-black p-2 sm:p-4">
            {liveView?.status === "ready" && liveView.stream_path ? (
              // biome-ignore lint/performance/noImgElement: MJPEG live streams are rendered by the browser image decoder.
              <img
                alt="UI 自动化实时浏览器画面"
                className="block h-full w-full object-contain"
                height={liveView.height}
                src={`${API_BASE_URL}${liveView.stream_path}`}
                width={liveView.width}
              />
            ) : null}
            {(liveViewLoading || liveView?.status === "waiting" || liveView?.status === "starting") &&
            liveView?.status !== "ready" ? (
              <div className="flex flex-col items-center gap-3 text-sm text-zinc-400">
                <Loader2 className="size-6 animate-spin" />
                <span>{liveView?.message ?? "正在连接浏览器画面"}</span>
              </div>
            ) : null}
            {liveView?.status === "unavailable" || liveView?.status === "ended" ? (
              <div className="flex max-w-md flex-col items-center gap-3 px-6 text-center text-sm text-zinc-400">
                <MonitorPlay className="size-8 text-zinc-500" />
                <span>{liveView.message}</span>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function ExecutionResultPanel({
  detail,
  filteredIterations,
  selectedIteration,
  parameterQuery,
  iterationStatus,
  expandedSteps,
  artifactUrls,
  onParameterQueryChange,
  onIterationStatusChange,
  onSelectIteration,
  onToggleStep,
}: {
  detail: UiAutomationRunDetailData | null;
  filteredIterations: UiAutomationIterationResult[];
  selectedIteration: UiAutomationIterationResult | null;
  parameterQuery: string;
  iterationStatus: string;
  expandedSteps: Set<string>;
  artifactUrls: Record<string, string>;
  onParameterQueryChange: (value: string) => void;
  onIterationStatusChange: (value: string) => void;
  onSelectIteration: (value: string) => void;
  onToggleStep: (value: string) => void;
}) {
  if (!detail?.detail_available) {
    return (
      <section className="border-y py-5">
        <SectionTitle title="参数与步骤结果" />
        <div className="flex min-h-24 items-center justify-center border bg-muted/20 px-4 text-center text-muted-foreground text-sm">
          当前运行尚未产生结构化步骤结果，仍可查看原始日志、截图和浏览器画面。
        </div>
      </section>
    );
  }

  const summary = detail.summary;
  const multipleIterations = Number(summary.total ?? 0) > 1;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <SectionTitle title="参数与步骤结果" />
        <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs tabular-nums">
          <SummaryValue label="总计" value={summary.total ?? 0} />
          <SummaryValue label="通过" tone="text-emerald-600 dark:text-emerald-400" value={summary.passed ?? 0} />
          <SummaryValue label="失败" tone="text-red-600 dark:text-red-400" value={summary.failed ?? 0} />
          <SummaryValue label="运行中" tone="text-amber-600 dark:text-amber-400" value={summary.running ?? 0} />
          <SummaryValue label="已停止" value={summary.cancelled ?? 0} />
        </div>
      </div>

      <div className={multipleIterations ? "grid min-h-[34rem] border lg:grid-cols-[20rem_minmax(0,1fr)]" : "border"}>
        {multipleIterations ? (
          <aside className="flex min-h-0 flex-col border-b bg-muted/10 lg:border-r lg:border-b-0">
            <div className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2 border-b p-3">
              <div className="relative">
                <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="筛选参数实例"
                  className="pl-8"
                  onChange={(event) => onParameterQueryChange(event.target.value)}
                  placeholder="筛选参数"
                  value={parameterQuery}
                />
              </div>
              <Select onValueChange={onIterationStatusChange} value={iterationStatus}>
                <SelectTrigger aria-label="按状态筛选参数实例" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="running">执行中</SelectItem>
                  <SelectItem value="passed">通过</SelectItem>
                  <SelectItem value="failed">失败</SelectItem>
                  <SelectItem value="infrastructure_error">环境错误</SelectItem>
                  <SelectItem value="cancelled">已停止</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="max-h-[42rem] min-h-0 overflow-y-auto p-1.5">
              {filteredIterations.length ? (
                <IterationList
                  iterations={filteredIterations}
                  onSelect={onSelectIteration}
                  selectedIterationId={selectedIteration?.iteration_id ?? ""}
                />
              ) : (
                <div className="flex min-h-32 items-center justify-center px-4 text-center text-muted-foreground text-xs">
                  没有符合筛选条件的参数实例
                </div>
              )}
            </div>
          </aside>
        ) : null}

        <div className="min-w-0">
          {selectedIteration ? (
            <IterationSteps
              artifactUrls={artifactUrls}
              expandedSteps={expandedSteps}
              iteration={selectedIteration}
              onToggleStep={onToggleStep}
            />
          ) : (
            <div className="flex min-h-72 items-center justify-center text-muted-foreground text-sm">
              请选择参数实例
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const ITERATION_ROW_HEIGHT = 48;
const VIRTUALIZATION_THRESHOLD = 100;
const VIRTUALIZATION_OVERSCAN = 6;

function IterationList({
  iterations,
  selectedIterationId,
  onSelect,
}: {
  iterations: UiAutomationIterationResult[];
  selectedIterationId: string;
  onSelect: (value: string) => void;
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const shouldVirtualize = iterations.length > VIRTUALIZATION_THRESHOLD;
  const viewportHeight = 42 * 16 - 12;
  const start = shouldVirtualize
    ? Math.max(0, Math.floor(scrollTop / ITERATION_ROW_HEIGHT) - VIRTUALIZATION_OVERSCAN)
    : 0;
  const end = shouldVirtualize
    ? Math.min(
        iterations.length,
        Math.ceil((scrollTop + viewportHeight) / ITERATION_ROW_HEIGHT) + VIRTUALIZATION_OVERSCAN,
      )
    : iterations.length;
  const visibleIterations = iterations.slice(start, end);

  const items = visibleIterations.map((iteration, visibleIndex) => (
    <IterationButton
      iteration={iteration}
      key={iteration.iteration_id}
      onSelect={onSelect}
      ordinal={start + visibleIndex + 1}
      selected={selectedIterationId === iteration.iteration_id}
      style={
        shouldVirtualize
          ? {
              height: ITERATION_ROW_HEIGHT,
              position: "absolute",
              top: (start + visibleIndex) * ITERATION_ROW_HEIGHT,
            }
          : undefined
      }
    />
  ));

  if (!shouldVirtualize) return items;

  return (
    <div
      className="relative -m-1.5 max-h-[42rem] overflow-y-auto p-1.5"
      onScroll={(event: UIEvent<HTMLDivElement>) => setScrollTop(event.currentTarget.scrollTop)}
      style={{ height: viewportHeight }}
    >
      <div className="relative" style={{ height: iterations.length * ITERATION_ROW_HEIGHT }}>
        {items}
      </div>
    </div>
  );
}

function IterationButton({
  iteration,
  ordinal,
  selected,
  onSelect,
  style,
}: {
  iteration: UiAutomationIterationResult;
  ordinal: number;
  selected: boolean;
  onSelect: (value: string) => void;
  style?: CSSProperties;
}) {
  return (
    <button
      className={`grid w-full grid-cols-[auto_auto_minmax(0,1fr)_auto] items-center gap-2 px-2.5 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected ? "bg-accent text-accent-foreground" : "hover:bg-muted/70"
      }`}
      onClick={() => onSelect(iteration.iteration_id)}
      style={style}
      type="button"
    >
      <IterationStatusIcon status={iteration.status} />
      <span className="font-mono text-muted-foreground text-xs tabular-nums">{ordinal}.</span>
      <span className="min-w-0 truncate font-medium text-xs leading-5">{parameterSummary(iteration)}</span>
      <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
        {formatDuration(iteration.duration_ms)}
      </span>
    </button>
  );
}

function IterationSteps({
  iteration,
  expandedSteps,
  artifactUrls,
  onToggleStep,
}: {
  iteration: UiAutomationIterationResult;
  expandedSteps: Set<string>;
  artifactUrls: Record<string, string>;
  onToggleStep: (value: string) => void;
}) {
  const visibleSteps = iteration.steps.filter((step) => step.visible);
  const legacyTechnicalSteps =
    visibleSteps.length > 0 &&
    visibleSteps.every(
      (step) =>
        step.title === step.step_id && step.operation_ids.length === 1 && step.operation_ids[0] === step.step_id,
    );
  return (
    <div>
      <header className="border-b px-4 py-3.5 sm:px-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-sm">{parameterSummary(iteration)}</h3>
          <StatusBadge tone={chineseCompletionTone(iteration.status)}>
            {iterationStatusLabel(iteration.status)}
          </StatusBadge>
          <span className="font-mono text-muted-foreground text-xs tabular-nums">
            {formatDuration(iteration.duration_ms)}
          </span>
        </div>
        {legacyTechnicalSteps ? (
          <p className="mt-2 text-amber-700 text-xs dark:text-amber-300">
            旧版资产缺少业务步骤映射，当前按技术动作展示；重新生成资产后可查看业务步骤名称与动作分组。
          </p>
        ) : null}
      </header>

      {visibleSteps.length ? (
        <div className="divide-y">
          {visibleSteps.map((step, index) => {
            const expanded = expandedSteps.has(step.step_id);
            const hasDetails = Boolean(step.error || step.artifacts.length || step.operation_ids.length);
            return (
              <article key={`${iteration.iteration_id}-${step.step_id}`}>
                <button
                  className="grid w-full grid-cols-[1.25rem_minmax(0,1fr)_auto_auto] items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset sm:px-5"
                  disabled={!hasDetails}
                  onClick={() => onToggleStep(step.step_id)}
                  type="button"
                >
                  <StepStatusIcon status={step.status} />
                  <span className="min-w-0">
                    <span className="block font-medium text-sm leading-5">
                      {index + 1}. {step.title || step.step_id}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-muted-foreground">
                      <span className="font-mono">{step.step_id}</span>
                      <span aria-hidden="true"> · </span>
                      <span>{stepResultLabel(step)}</span>
                    </span>
                  </span>
                  <span className="pt-0.5 font-mono text-muted-foreground text-xs tabular-nums">
                    {formatDuration(step.duration_ms)}
                  </span>
                  {hasDetails ? (
                    expanded ? (
                      <ChevronDown className="mt-0.5 size-4" />
                    ) : (
                      <ChevronRight className="mt-0.5 size-4" />
                    )
                  ) : (
                    <span className="size-4" />
                  )}
                </button>
                {expanded && hasDetails ? <StepDetails artifactUrls={artifactUrls} step={step} /> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="flex min-h-64 items-center justify-center p-5">
          {iteration.error ? (
            <div className="w-full max-w-3xl border-red-500 border-l-2 px-4 py-3">
              <div className="font-medium text-red-700 text-sm dark:text-red-300">
                {iteration.error.type ?? "步骤开始前执行失败"}
              </div>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap font-mono text-red-700 text-xs leading-5 dark:text-red-200">
                {iteration.error.message ?? "参数实例在进入业务步骤前失败。"}
              </pre>
              <p className="mt-2 text-muted-foreground text-xs">该错误发生在首个业务步骤开始前。</p>
            </div>
          ) : (
            <span className="text-muted-foreground text-sm">该实例暂无步骤事件</span>
          )}
        </div>
      )}
    </div>
  );
}

function StepDetails({ step, artifactUrls }: { step: UiAutomationStepResult; artifactUrls: Record<string, string> }) {
  return (
    <div className="space-y-3 bg-muted/20 px-4 pt-1 pb-4 sm:pl-12">
      {step.error ? (
        <div className="border-red-500 border-l-2 px-3 py-2">
          <div className="font-medium text-red-700 text-xs dark:text-red-300">{step.error.type ?? "执行失败"}</div>
          <pre className="mt-1 overflow-auto whitespace-pre-wrap font-mono text-red-700 text-xs leading-5 dark:text-red-200">
            {step.error.message ?? "步骤执行失败"}
          </pre>
        </div>
      ) : null}
      {step.operation_ids.length ? (
        <div>
          <div className="mb-1.5 text-muted-foreground text-xs">技术动作</div>
          <div className="flex flex-wrap gap-1.5">
            {step.operation_ids.map((operationId) => (
              <code className="border bg-background px-1.5 py-1 text-[10px]" key={operationId}>
                {operationId}
              </code>
            ))}
          </div>
        </div>
      ) : null}
      {step.artifacts.map((artifact) =>
        artifactUrls[artifact.artifact_id] ? (
          <figure className="max-w-3xl overflow-hidden border bg-background" key={artifact.artifact_id}>
            {/* biome-ignore lint/performance/noImgElement: authenticated evidence is loaded as a blob URL. */}
            <img
              alt={`${step.title || step.step_id}失败截图`}
              className="aspect-video w-full object-contain"
              src={artifactUrls[artifact.artifact_id]}
            />
            <figcaption className="border-t px-3 py-2 font-mono text-[10px] text-muted-foreground">
              {artifact.artifact_id}
            </figcaption>
          </figure>
        ) : null,
      )}
    </div>
  );
}

function SummaryValue({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <span className={tone}>
      <span className="text-muted-foreground">{label}</span> {value}
    </span>
  );
}

function IterationStatusIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="mt-0.5 size-4 animate-spin text-amber-500" />;
  if (status === "passed") return <CheckCircle2 className="mt-0.5 size-4 text-emerald-500" />;
  if (status === "failed" || status === "infrastructure_error") {
    return <XCircle className="mt-0.5 size-4 text-red-500" />;
  }
  if (status === "cancelled") return <Square className="mt-0.5 size-3.5 text-muted-foreground" />;
  return <Circle className="mt-0.5 size-4 text-muted-foreground" />;
}

function StepStatusIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 className="mt-0.5 size-4 animate-spin text-amber-500" />;
  if (status === "passed") return <CheckCircle2 className="mt-0.5 size-4 text-emerald-500" />;
  if (status === "failed") return <XCircle className="mt-0.5 size-4 text-red-500" />;
  if (status === "cancelled") return <Square className="mt-0.5 size-3.5 text-muted-foreground" />;
  return <Clock3 className="mt-0.5 size-4 text-muted-foreground" />;
}

function stepResultLabel(step: UiAutomationStepResult) {
  if (step.status === "cancelled") return step.started_at ? "执行中被停止" : "因运行停止未执行";
  return (
    {
      pending: "等待执行",
      running: "执行中",
      passed: "通过",
      failed: "失败",
      skipped: "已跳过",
    }[step.status] ?? step.status
  );
}

function parameterSummary(iteration: UiAutomationIterationResult) {
  const entries = Object.entries(iteration.parameters);
  if (entries.length === 0) return "默认参数实例";
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(" · ");
}

function formatDuration(value: number | null) {
  if (value === null || !Number.isFinite(value)) return "-";
  if (value < 1000) return `${Math.round(value)}ms`;
  if (value < 60_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}s`;
  return `${Math.floor(value / 60_000)}m ${Math.round((value % 60_000) / 1000)}s`;
}

function iterationStatusLabel(status: string) {
  return (
    {
      pending: "等待中",
      running: "执行中",
      passed: "通过",
      failed: "失败",
      skipped: "已跳过",
      cancelled: "已停止",
      infrastructure_error: "环境错误",
    }[status] ?? status
  );
}

function LiveStatus({ status }: { status: UiAutomationLiveView["status"] }) {
  const isLive = status === "ready";
  return (
    <span
      className={`inline-flex h-6 items-center gap-1.5 rounded-full border px-2 text-xs ${
        isLive ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-zinc-700 text-zinc-400"
      }`}
    >
      <Radio className={`size-3 ${isLive ? "animate-pulse" : ""}`} />
      {isLive ? "直播中" : status === "ended" ? "已结束" : status === "unavailable" ? "不可用" : "连接中"}
    </span>
  );
}

function statusLabel(status: string) {
  return (
    (
      {
        queued: "排队中",
        running: "执行中",
        stopping: "停止中",
        passed: "通过",
        failed: "失败",
        cancelled: "已停止",
      } as Record<string, string>
    )[status] ?? status
  );
}

function DetailValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={mono ? "mt-1 truncate font-mono text-xs" : "mt-1 truncate font-medium text-sm"} title={value}>
        {value}
      </div>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return <h2 className="mb-3 font-semibold text-sm">{title}</h2>;
}
