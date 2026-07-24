"use client";

import { useCallback, useEffect, useState } from "react";

import { Bot, LoaderCircle, RefreshCw, ShieldCheck, WandSparkles } from "lucide-react";
import { toast } from "sonner";

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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import {
  ApiRequestError,
  applyPerformanceAnalysis,
  createPerformanceAnalysis,
  getPerformanceAnalysis,
  listPerformanceRunAnalyses,
  type PerformanceAnalysis,
} from "@/lib/api-client";

import { PerformanceAiAnalysisProgress } from "./performance-ai-analysis-progress";
import { PerformanceAiConfigDiff } from "./performance-ai-config-diff";
import { PerformanceAiEvidenceList } from "./performance-ai-evidence-list";

const ACTIVE_STATUSES = new Set<PerformanceAnalysis["status"]>(["collecting", "analyzing"]);

export function PerformanceAiAnalysisDrawer({
  projectId,
  runId,
  open,
  onOpenChange,
  onRepairApplied,
}: {
  projectId: string;
  runId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRepairApplied?: (runId: string) => void;
}) {
  const [analysis, setAnalysis] = useState<PerformanceAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [repairing, setRepairing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [selectedChangeIds, setSelectedChangeIds] = useState<string[]>([]);

  useEffect(() => {
    if (!analysis) return;
    setSelectedChangeIds(
      analysis.selected_change_ids.length ? analysis.selected_change_ids : analysis.applicable_change_ids,
    );
  }, [analysis]);

  const refresh = useCallback(
    async (analysisId: string) => {
      const next = await getPerformanceAnalysis(projectId, analysisId);
      setAnalysis(next);
      return next;
    },
    [projectId],
  );

  const create = useCallback(async () => {
    setWorking(true);
    try {
      const next = await createPerformanceAnalysis(projectId, runId);
      setAnalysis(next);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setWorking(false);
    }
  }, [projectId, runId]);

  useEffect(() => {
    if (!open) return;
    let disposed = false;
    setLoading(true);
    listPerformanceRunAnalyses(projectId, runId)
      .then((items) => {
        if (disposed) return;
        if (items[0]) setAnalysis(items[0]);
        else void create();
      })
      .catch((error) => !disposed && toast.error(apiErrorMessage(error)))
      .finally(() => !disposed && setLoading(false));
    return () => {
      disposed = true;
    };
  }, [create, open, projectId, runId]);

  useEffect(() => {
    if (!open || !analysis || !ACTIVE_STATUSES.has(analysis.status)) return;
    const timer = window.setInterval(() => {
      void refresh(analysis.id).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [analysis, open, refresh]);

  async function applyRepair() {
    if (!analysis) return;
    setRepairing(true);
    try {
      const next = await applyPerformanceAnalysis(projectId, analysis.id, selectedChangeIds);
      setAnalysis(next);
      if (next.application_status === "completed" && next.applied_run_id) {
        toast.success("AI 修复已应用，新的压测已启动");
        onOpenChange(false);
        onRepairApplied?.(next.applied_run_id);
      } else if (next.application_status === "preflight_failed") {
        toast.error("修复预检失败，原配置未修改");
      }
    } catch (error) {
      toast.error(apiErrorMessage(error));
      if (analysis) void refresh(analysis.id).catch(() => undefined);
    } finally {
      setRepairing(false);
      setConfirmOpen(false);
    }
  }

  return (
    <Drawer direction="right" onOpenChange={onOpenChange} open={open}>
      <DrawerContent className="h-full w-full data-[vaul-drawer-direction=right]:sm:max-w-3xl">
        <DrawerHeader className="border-b pr-14">
          <div className="flex items-center gap-2">
            <Bot className="size-5 text-blue-600" />
            <DrawerTitle>性能压测 AI 分析</DrawerTitle>
            {analysis ? <Badge variant="outline">第 {analysis.analysis_version} 次</Badge> : null}
          </div>
          <DrawerDescription>运行 {runId} · 审批后自动预检、修复配置并重新压测</DrawerDescription>
        </DrawerHeader>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {loading && !analysis ? (
            <div className="flex min-h-48 items-center justify-center text-muted-foreground text-sm">
              <LoaderCircle className="mr-2 size-4 animate-spin" /> 正在加载分析记录
            </div>
          ) : null}
          {analysis ? (
            <div className="space-y-6">
              <PerformanceAiAnalysisProgress status={analysis.status} />
              {analysis.status === "failed" ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
                  {analysisFailureMessage(analysis.error_message)}
                </div>
              ) : null}
              {analysis.direct_cause ? (
                <section className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{categoryLabel(analysis.category)}</Badge>
                    <Badge variant="outline">置信度 {Math.round(analysis.confidence * 100)}%</Badge>
                    {analysis.model_name ? <Badge variant="secondary">{analysis.model_name}</Badge> : null}
                  </div>
                  <DiagnosisBlock label="直接原因" value={analysis.direct_cause} />
                  <DiagnosisBlock label="根因判断" value={analysis.root_cause} />
                </section>
              ) : null}
              <PerformanceAiEvidenceList evidence={analysis.evidence} />
              {analysis.missing_evidence.length ? (
                <section>
                  <h3 className="mb-2 font-semibold text-sm">缺失证据</h3>
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground text-xs">
                    {analysis.missing_evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </section>
              ) : null}
              <PerformanceAiConfigDiff
                applicableChangeIds={analysis.applicable_change_ids}
                changes={analysis.proposal.changes ?? []}
                onSelectionChange={setSelectedChangeIds}
                selectedChangeIds={selectedChangeIds}
              />
              <ApplicationResult analysis={analysis} />
              <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-800 text-xs dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-200">
                <ShieldCheck className="mt-0.5 size-4 shrink-0" />
                认证信息不会由 AI 写入；修复仅应用选中的白名单配置，并在单请求预检通过后启动新压测。
              </div>
            </div>
          ) : null}
        </div>

        <DrawerFooter className="flex-row justify-end border-t">
          {analysis?.available_actions.includes("apply_and_rerun") ? (
            <Button disabled={repairing || selectedChangeIds.length === 0} onClick={() => setConfirmOpen(true)}>
              <WandSparkles className="mr-2 size-4" />
              修复并重新压测
            </Button>
          ) : null}
          <Button
            variant="outline"
            disabled={working || Boolean(analysis && ACTIVE_STATUSES.has(analysis.status))}
            onClick={() => void create()}
          >
            <RefreshCw className={working ? "mr-2 size-4 animate-spin" : "mr-2 size-4"} />
            重新分析
          </Button>
        </DrawerFooter>
        <AlertDialog onOpenChange={setConfirmOpen} open={confirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>应用 AI 修复并重新压测？</AlertDialogTitle>
              <AlertDialogDescription>
                将应用 {selectedChangeIds.length}{" "}
                项已选配置，先发送一次预检请求。预检通过后保存新脚本版本并自动启动压测；失败时保留原配置。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction disabled={repairing} onClick={() => void applyRepair()}>
                {repairing ? (
                  <LoaderCircle className="mr-2 size-4 animate-spin" />
                ) : (
                  <WandSparkles className="mr-2 size-4" />
                )}
                确认修复
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </DrawerContent>
    </Drawer>
  );
}

function ApplicationResult({ analysis }: { analysis: PerformanceAnalysis }) {
  if (analysis.application_status === "not_requested") return null;
  const labels: Record<string, string> = {
    preflighting: "正在执行单请求预检",
    preflight_failed: "预检失败，未应用修复",
    rerunning: "修复已应用，正在启动新压测",
    completed: "修复完成，新压测已启动",
    apply_failed: "修复应用或重跑启动失败",
    superseded: "原配置已变化，需要重新分析",
  };
  return (
    <section className="space-y-2 rounded-lg border p-3 text-sm">
      <h3 className="font-semibold">{labels[analysis.application_status] ?? analysis.application_status}</h3>
      {analysis.preflight.status_code !== undefined ? (
        <p className="text-muted-foreground text-xs">
          预检状态码：{analysis.preflight.status_code ?? "无响应"}
          {analysis.preflight.final_url ? ` · ${analysis.preflight.final_url}` : ""}
        </p>
      ) : null}
      {(analysis.preflight.failures ?? []).map((failure) => (
        <p className="text-destructive text-xs" key={failure}>
          {failure}
        </p>
      ))}
    </section>
  );
}

function DiagnosisBlock({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <h3 className="mb-1 font-semibold text-sm">{label}</h3>
      <p className="whitespace-pre-wrap text-muted-foreground text-sm leading-6">{value}</p>
    </div>
  );
}

function categoryLabel(value: string) {
  const labels: Record<string, string> = {
    performance_config: "压测配置",
    locust_script: "Locust 脚本",
    platform_code: "平台代码",
    external_service: "外部服务",
    insufficient_evidence: "证据不足",
  };
  return labels[value] ?? "分析中";
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  }
  return error instanceof Error ? error.message : "AI 分析请求失败";
}

function analysisFailureMessage(errorMessage: string) {
  if (/rate[ _-]?limit/i.test(errorMessage)) {
    return "AI 分析执行失败：触发模型接口 429 频率限制，可能是请求过于频繁或模型配额不足。请稍后重试或检查模型配额。";
  }
  return errorMessage || "AI 分析失败，请稍后重新分析。";
}
