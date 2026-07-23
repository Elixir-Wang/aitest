"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { ArrowLeft, Download, ImageIcon, Loader2, MonitorPlay, Play, Radio, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import {
  API_BASE_URL,
  apiBlobRequest,
  createUiAutomationExecutionRun,
  formatDateTime,
  getUiAutomationExecutionRun,
  getUiAutomationLiveView,
  getUiAutomationRunLogs,
  type UiAutomationExecutionRun,
  type UiAutomationLiveView,
} from "@/lib/api-client";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";

const activeStatuses = new Set(["queued", "running"]);

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
  const [logs, setLogs] = useState({ stdout: "", stderr: "" });
  const [screenshotUrls, setScreenshotUrls] = useState<string[]>([]);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);
  const [liveViewOpen, setLiveViewOpen] = useState(false);
  const [liveView, setLiveView] = useState<UiAutomationLiveView | null>(null);
  const [liveViewLoading, setLiveViewLoading] = useState(false);

  const loadDetail = useCallback(
    async (showLoading = true) => {
      if (showLoading) setLoading(true);
      try {
        const nextRun = await getUiAutomationExecutionRun(projectId, runId);
        setRun(nextRun);
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

  useEffect(() => {
    if (!run?.video_path || activeStatuses.has(run.status)) return;
    let disposed = false;
    let url = "";
    void apiBlobRequest(`/projects/${projectId}/ui-automation/runs/${runId}/artifacts/video`)
      .then((blob) => {
        if (disposed) return;
        url = URL.createObjectURL(blob);
        setVideoUrl(url);
      })
      .catch(() => setVideoUrl(null));
    return () => {
      disposed = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [projectId, run, runId]);

  async function downloadTrace() {
    try {
      const blob = await apiBlobRequest(`/projects/${projectId}/ui-automation/runs/${runId}/artifacts/trace`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${runId}-trace.zip`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Trace 下载失败");
    }
  }

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
            <Button
              disabled={!run || activeStatuses.has(run.status) || rerunning}
              onClick={() => void rerun()}
              variant="outline"
            >
              {rerunning ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              重新执行
            </Button>
            <Button disabled={!run} onClick={() => setLiveViewOpen(true)} variant="outline">
              <MonitorPlay className="size-4" />
              {activeStatuses.has(run?.status ?? "") ? "实时查看" : "浏览器回放"}
            </Button>
            {run?.trace_path ? (
              <Button onClick={() => void downloadTrace()} variant="outline">
                <Download className="size-4" />
                下载 Trace
              </Button>
            ) : null}
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
              <DetailValue label="运行环境" mono value={run.environment_id} />
              <DetailValue label="开始时间" value={formatDateTime(run.started_at || run.created_at)} />
              <DetailValue label="完成时间" value={run.finished_at ? formatDateTime(run.finished_at) : "-"} />
              <DetailValue label="退出码" value={String(run.result.exitcode ?? "-")} />
              <DetailValue label="截图" value={String(run.screenshot_paths.length)} />
              <DetailValue label="Trace" value={run.trace_path ? "已保存" : "未生成"} />
              <DetailValue label="执行人" mono value={run.created_by} />
            </div>

            {run.error_message ? (
              <section>
                <SectionTitle title="失败原因" />
                <pre className="overflow-auto whitespace-pre-wrap rounded-md border border-red-200 bg-red-50 p-3 text-red-800 text-xs dark:border-red-900 dark:bg-red-950/30 dark:text-red-200">
                  {run.error_message}
                </pre>
              </section>
            ) : null}

            <section>
              <SectionTitle title="运行日志" />
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
              {videoUrl ? (
                <video className="mb-4 aspect-video w-full rounded-md border bg-black" controls src={videoUrl}>
                  <track kind="captions" label="执行步骤" src="data:text/vtt,WEBVTT" srcLang="zh-CN" />
                </video>
              ) : null}
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

      <Dialog onOpenChange={setLiveViewOpen} open={liveViewOpen}>
        <DialogContent className="grid h-[min(58rem,calc(100dvh-2rem))] w-[calc(100vw-2rem)] max-w-none grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden bg-zinc-950 p-0 text-zinc-100 sm:max-w-7xl">
          <DialogHeader className="border-zinc-800 border-b px-5 py-4 pr-14">
            <div className="flex flex-wrap items-center gap-3">
              <DialogTitle className="text-zinc-100">浏览器操作过程</DialogTitle>
              <LiveStatus status={liveView?.status ?? (liveViewLoading ? "starting" : "waiting")} />
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
                className="max-h-full max-w-full object-contain"
                height={liveView.height}
                src={`${API_BASE_URL}${liveView.stream_path}`}
                width={liveView.width}
              />
            ) : null}
            {liveView?.status === "ended" && videoUrl ? (
              <video className="max-h-full max-w-full" controls src={videoUrl}>
                <track kind="captions" label="执行步骤" src="data:text/vtt,WEBVTT" srcLang="zh-CN" />
              </video>
            ) : null}
            {(liveViewLoading || liveView?.status === "waiting" || liveView?.status === "starting") &&
            liveView?.status !== "ready" ? (
              <div className="flex flex-col items-center gap-3 text-zinc-400 text-sm">
                <Loader2 className="size-6 animate-spin" />
                <span>{liveView?.message ?? "正在连接浏览器画面"}</span>
              </div>
            ) : null}
            {liveView?.status === "unavailable" || (liveView?.status === "ended" && !videoUrl) ? (
              <div className="flex max-w-md flex-col items-center gap-3 px-6 text-center text-zinc-400 text-sm">
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
        passed: "通过",
        failed: "失败",
        cancelled: "已取消",
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
