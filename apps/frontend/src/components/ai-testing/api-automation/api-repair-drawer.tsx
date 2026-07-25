"use client";

import { useCallback, useEffect, useState } from "react";

import {
  ArrowRight,
  Bot,
  Check,
  CircleCheck,
  FileCode2,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "@/lib/toast";

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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type ApiAutomationRun,
  type ApiRepairSession,
  applyApiRepairAttempt,
  approveApiRepairAttempt,
  createApiRepairAttempt,
  createApiRepairSession,
  discardApiRepairAttempt,
  getApiRepairAttemptDiff,
  getApiRepairSession,
  rejectApiRepairAttempt,
} from "@/lib/api-client";

import { ApiRepairDiffDialog } from "./api-repair-diff-dialog";
import { ApiRepairProgress, apiRepairStatusLabel } from "./api-repair-progress";

const ACTIVE_STATUSES = new Set([
  "queued",
  "collecting_context",
  "diagnosing",
  "candidate_generating",
  "candidate_validating",
  "applying",
  "rerunning",
]);

function localizeRepairText(value: string) {
  return value.replace(/\bOracle\b/g, "测试预期");
}

export function ApiRepairDrawer({
  projectId,
  run,
  open,
  onOpenChange,
  onRunChanged,
}: {
  projectId: string;
  run: ApiAutomationRun;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRunChanged: () => void;
}) {
  const [session, setSession] = useState<ApiRepairSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [working, setWorking] = useState(false);
  const [diffOpen, setDiffOpen] = useState(false);
  const [diff, setDiff] = useState("");
  const [diffError, setDiffError] = useState("");
  const [diffLoading, setDiffLoading] = useState(false);
  const attempt = session?.attempts.at(-1) ?? null;

  const refresh = useCallback(
    async (sessionId: string) => {
      const next = await getApiRepairSession(projectId, sessionId);
      setSession(next);
      return next;
    },
    [projectId],
  );

  const start = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const created = await createApiRepairSession(projectId, run.id);
      await refresh(created.session_id);
    } catch (error) {
      const message = errorMessage(error, "AI 修复任务创建失败");
      setLoadError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [projectId, refresh, run.id]);

  useEffect(() => {
    if (!open || session || loading || loadError) return;
    void start();
  }, [loadError, loading, open, session, start]);

  useEffect(() => {
    if (!open || !session?.id || !attempt || !ACTIVE_STATUSES.has(attempt.status)) return;
    const timer = window.setInterval(() => {
      void refresh(session.id).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [attempt, open, refresh, session?.id]);

  async function approve() {
    if (!attempt || !session) return;
    setWorking(true);
    try {
      await approveApiRepairAttempt(projectId, attempt.id);
      toast.success("修复建议已批准，正在生成候选测试脚本");
      await refresh(session.id);
    } catch (error) {
      toast.error(errorMessage(error, "修复建议审批失败"));
    } finally {
      setWorking(false);
    }
  }

  async function reanalyze() {
    if (!session) return;
    setWorking(true);
    try {
      await createApiRepairAttempt(projectId, session.id);
      toast.success("已开始新一轮失败分析");
      await refresh(session.id);
    } catch (error) {
      toast.error(errorMessage(error, "重新分析失败"));
    } finally {
      setWorking(false);
    }
  }

  async function applyCandidate() {
    if (!attempt || !session) return;
    setWorking(true);
    try {
      await applyApiRepairAttempt(projectId, attempt.id);
      toast.success("测试脚本已应用，正在执行正式接口回归");
      await refresh(session.id);
      onRunChanged();
    } catch (error) {
      toast.error(errorMessage(error, "候选测试脚本应用失败"));
    } finally {
      setWorking(false);
    }
  }

  async function discardCandidate() {
    if (!attempt || !session) return;
    setWorking(true);
    try {
      await discardApiRepairAttempt(projectId, attempt.id, "");
      toast.success("候选修复已放弃，正式测试脚本未修改");
      await refresh(session.id);
    } catch (error) {
      toast.error(errorMessage(error, "候选修复放弃失败"));
    } finally {
      setWorking(false);
    }
  }

  async function reject() {
    if (!attempt || !session) return;
    setWorking(true);
    try {
      await rejectApiRepairAttempt(projectId, attempt.id, "");
      await refresh(session.id);
    } catch (error) {
      toast.error(errorMessage(error, "修复方案拒绝失败"));
    } finally {
      setWorking(false);
    }
  }

  async function openDiff() {
    if (!attempt) return;
    setDiffOpen(true);
    setDiffLoading(true);
    setDiffError("");
    try {
      const result = await getApiRepairAttemptDiff(projectId, attempt.id);
      setDiff(result.diff);
    } catch (error) {
      setDiffError(errorMessage(error, "候选修改加载失败"));
    } finally {
      setDiffLoading(false);
    }
  }

  const attemptActions = new Set(attempt?.available_actions ?? []);
  const proposal = attempt?.diagnosis?.proposal;
  const oracleCalibration = Boolean(proposal?.case_updates?.length);
  const recommendations = (attempt?.diagnosis?.issues ?? [])
    .map((issue) => issue.recommendation?.trim())
    .filter((recommendation): recommendation is string => Boolean(recommendation));
  const summary = attempt?.validation?.summary ?? {};
  const passed = summary.passed ?? 0;
  const failed = summary.failed ?? 0;
  const diagnosisOnly = attempt?.status === "proposal_ready";
  const candidateResult = Boolean(
    attempt && ["ready_to_apply", "applying", "rerunning", "completed"].includes(attempt.status),
  );
  const hasActions = attemptActions.size > 0;
  const diagnosisCategory = attempt?.diagnosis?.issues?.[0]?.classification;
  const caseUpdates = proposal?.case_updates ?? [];
  const diagnosisOutcome =
    diagnosisCategory === "interface_bug"
      ? "当前失败来自被测接口行为，不是测试脚本错误。本轮分析到此结束，请根据下方诊断结果处理接口缺陷。"
      : diagnosisCategory === "environment_issue"
        ? "当前失败更可能来自测试环境，不是测试脚本错误。本轮分析到此结束，请先恢复环境后重新执行。"
        : "本轮诊断未生成可安全应用的测试代码修改方案，测试脚本保持不变。请根据下方诊断结果处理问题。";

  return (
    <>
      <Drawer direction="right" onOpenChange={onOpenChange} open={open}>
        <DrawerContent className="h-full data-[vaul-drawer-direction=right]:w-full sm:data-[vaul-drawer-direction=right]:max-w-5xl">
          <DrawerHeader className="border-b pr-14">
            <div className="flex flex-wrap items-center gap-2">
              <Bot className="size-5 text-blue-600" />
              <DrawerTitle>接口自动化 AI 分析与修复</DrawerTitle>
              {attempt ? <Badge variant="outline">第 {attempt.attempt_number} 轮</Badge> : null}
              {attempt ? <Badge variant="secondary">{apiRepairStatusLabel(attempt.status)}</Badge> : null}
            </div>
            <DrawerDescription>
              运行 {run.id} ·{" "}
              {diagnosisOnly ? "已完成失败归因，测试代码未修改" : "确认后生成候选修改，验证通过后再应用正式测试代码"}
            </DrawerDescription>
          </DrawerHeader>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {loading && !session ? (
              <div className="flex min-h-48 items-center justify-center text-muted-foreground text-sm">
                <Loader2 className="mr-2 size-4 animate-spin" /> 正在创建或恢复 AI 修复会话
              </div>
            ) : null}

            {!loading && !session && loadError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
                {loadError}
              </div>
            ) : null}

            {attempt ? (
              <div className="space-y-6">
                <ApiRepairProgress status={attempt.status} />

                {diagnosisOnly ? (
                  <section className="flex gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-950 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-100">
                    <CircleCheck className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                    <div className="space-y-1">
                      <h3 className="font-semibold text-sm">诊断已完成，无需修改测试代码</h3>
                      <p className="text-emerald-800 text-sm leading-6 dark:text-emerald-200">{diagnosisOutcome}</p>
                    </div>
                  </section>
                ) : null}

                {attempt.error_message ? (
                  <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
                    {attempt.error_message}
                  </div>
                ) : null}

                {attempt.diagnosis?.summary ? (
                  <section className="overflow-hidden rounded-lg border bg-card">
                    <div className="flex items-center justify-between gap-3 border-b bg-muted/30 px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="flex size-7 items-center justify-center rounded-md border bg-background">
                          <Sparkles className="size-3.5 text-blue-600 dark:text-blue-400" />
                        </span>
                        <div>
                          <h3 className="font-semibold text-sm">诊断结果</h3>
                          <p className="text-muted-foreground text-xs">基于本次运行响应与测试断言生成</p>
                        </div>
                      </div>
                      {attempt.diagnosis.issues?.length ? (
                        <Badge className="rounded-md font-mono tabular-nums" variant="secondary">
                          {attempt.diagnosis.issues.length} 项发现
                        </Badge>
                      ) : null}
                    </div>
                    <p className="whitespace-pre-wrap px-4 py-4 text-foreground/85 text-sm leading-7">
                      {localizeRepairText(attempt.diagnosis.summary)}
                    </p>
                  </section>
                ) : null}

                {proposal ? (
                  <section className="overflow-hidden rounded-lg border border-amber-500/30 bg-card shadow-sm">
                    <div className="h-1 bg-amber-500" />
                    <div className="space-y-4 p-4 sm:p-5">
                      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                        <div className="flex min-w-0 gap-3">
                          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-amber-500/12 text-amber-700 dark:text-amber-400">
                            <ShieldAlert className="size-4.5" />
                          </span>
                          <div className="min-w-0 space-y-1">
                            <h3 className="font-semibold text-base">
                              {proposal.script_repair_allowed
                                ? oracleCalibration
                                  ? "待审批的用例预期调整"
                                  : "待确认的代码修改"
                                : "诊断结论"}
                            </h3>
                            <p className="text-muted-foreground text-sm leading-6">
                              {localizeRepairText(proposal.title)}
                            </p>
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {oracleCalibration ? (
                            <Badge
                              className="rounded-md bg-amber-500/12 text-amber-800 dark:text-amber-300"
                              variant="outline"
                            >
                              {caseUpdates.length} 条变更
                            </Badge>
                          ) : null}
                          <Badge className="rounded-md font-mono tabular-nums" variant="outline">
                            置信度 {Math.round(proposal.confidence * 100)}%
                          </Badge>
                        </div>
                      </div>

                      <p className="whitespace-pre-wrap border-amber-500/50 border-l-2 pl-3 text-foreground/80 text-sm leading-6">
                        {localizeRepairText(proposal.summary)}
                      </p>

                      {proposal.script_repair_allowed && oracleCalibration ? (
                        <div className="overflow-hidden rounded-md border">
                          <div className="flex items-center justify-between gap-3 border-b bg-muted/35 px-3 py-2.5">
                            <div className="flex items-center gap-2 font-medium text-sm">
                              <FileCode2 className="size-4 text-muted-foreground" />
                              用例预期变更
                            </div>
                            <span className="hidden text-muted-foreground text-xs sm:inline">
                              审批后同步测试用例并确认测试预期
                            </span>
                          </div>
                          <Table>
                            <TableHeader>
                              <TableRow className="hover:bg-transparent">
                                <TableHead className="w-12 pl-3 text-muted-foreground text-xs">#</TableHead>
                                <TableHead className="text-muted-foreground text-xs">用例 ID</TableHead>
                                <TableHead className="w-40 text-muted-foreground text-xs">状态码调整</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {caseUpdates.map((update, index) => (
                                <TableRow key={update.case_id}>
                                  <TableCell className="pl-3 font-mono text-muted-foreground text-xs tabular-nums">
                                    {String(index + 1).padStart(2, "0")}
                                  </TableCell>
                                  <TableCell className="max-w-0">
                                    <span className="block truncate font-mono text-xs" title={update.case_id}>
                                      {update.case_id}
                                    </span>
                                  </TableCell>
                                  <TableCell>
                                    <div className="flex items-center gap-2 font-mono font-semibold text-xs tabular-nums">
                                      <span className="rounded border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-amber-800 dark:text-amber-300">
                                        {update.expected_status_code}
                                      </span>
                                      <ArrowRight className="size-3.5 text-muted-foreground" />
                                      <span className="rounded border border-emerald-500/25 bg-emerald-500/10 px-2 py-1 text-emerald-800 dark:text-emerald-300">
                                        {update.actual_status_code}
                                      </span>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      ) : null}

                      {proposal.script_repair_allowed && !oracleCalibration && proposal.proposed_changes.length ? (
                        <div className="space-y-2 rounded-md border bg-muted/20 p-3 text-sm">
                          <div className="font-medium">拟修改代码</div>
                          {proposal.proposed_changes.map((item) => (
                            <div className="flex gap-2 text-muted-foreground" key={item}>
                              <span className="mt-2 size-1 shrink-0 rounded-full bg-blue-500" />
                              <p className="leading-6">{localizeRepairText(item)}</p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </section>
                ) : null}

                {diagnosisOnly && !proposal ? (
                  <section className="space-y-3 rounded-lg border bg-muted/20 p-4">
                    <div className="space-y-1">
                      <h3 className="font-semibold text-sm">处理建议</h3>
                      <p className="text-muted-foreground text-sm">
                        本轮诊断未生成可审批的测试代码修改方案，不会进入候选代码生成步骤。
                      </p>
                    </div>
                    {recommendations.length ? (
                      <div className="space-y-1 text-sm">
                        {recommendations.map((recommendation) => (
                          <p className="text-muted-foreground" key={recommendation}>
                            • {localizeRepairText(recommendation)}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ) : null}

                {attempt.validation?.summary ? (
                  <section className="space-y-3">
                    <h3 className="font-semibold text-sm">{candidateResult ? "候选修改验证结果" : "原运行结果"}</h3>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/20 dark:text-emerald-200">
                        通过：<span className="font-semibold tabular-nums">{passed}</span>
                      </div>
                      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-700 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200">
                        失败：<span className="font-semibold tabular-nums">{failed}</span>
                      </div>
                    </div>
                    {attempt.validation.changed_files?.length ? (
                      <p className="text-muted-foreground text-xs">
                        修改文件：{attempt.validation.changed_files.length} 个
                      </p>
                    ) : null}
                  </section>
                ) : null}
              </div>
            ) : null}
          </div>

          <DrawerFooter className="flex-row flex-wrap items-center justify-end border-t bg-background">
            {diagnosisOnly ? (
              <p className="mr-auto text-muted-foreground text-sm">诊断流程已结束，未修改任何测试代码。</p>
            ) : null}
            {attemptActions.has("approve_proposal") || attemptActions.has("reject_proposal") ? (
              <>
                {attemptActions.has("reject_proposal") ? (
                  <Button disabled={working} onClick={() => void reject()} variant="outline">
                    <X className="size-4" />
                    拒绝建议
                  </Button>
                ) : null}
                {attemptActions.has("approve_proposal") ? (
                  <Button disabled={working} onClick={() => void approve()}>
                    {working ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                    {oracleCalibration ? "批准调整预期" : "确认修改代码"}
                  </Button>
                ) : null}
              </>
            ) : null}
            {attemptActions.has("view_diff") ? (
              <Button disabled={working} onClick={() => void openDiff()} variant="outline">
                查看 Diff
              </Button>
            ) : null}
            {attemptActions.has("discard") ? (
              <Button disabled={working} onClick={() => void discardCandidate()} variant="outline">
                <X className="size-4" />
                放弃候选修复
              </Button>
            ) : null}
            {attemptActions.has("apply") ? (
              <Button disabled={working} onClick={() => void applyCandidate()}>
                {working ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                应用通过的测试脚本
              </Button>
            ) : null}
            {attempt && ACTIVE_STATUSES.has(attempt.status) ? (
              <div className="mr-auto flex items-center px-2 text-muted-foreground text-sm">
                <Loader2 className="mr-2 size-4 animate-spin" />
                AI 正在分析和验证
              </div>
            ) : null}
            {!attempt && loadError ? (
              <Button disabled={loading} onClick={() => void start()}>
                <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
                重试
              </Button>
            ) : null}
            {attemptActions.has("reanalyze") ? (
              <Button disabled={working} onClick={() => void reanalyze()}>
                {working ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                重新分析
              </Button>
            ) : null}
            {attempt && !ACTIVE_STATUSES.has(attempt.status) && (diagnosisOnly || !hasActions) ? (
              <Button onClick={() => onOpenChange(false)} variant="outline">
                <X className="size-4" />
                关闭
              </Button>
            ) : null}
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      <ApiRepairDiffDialog
        diff={diff}
        error={diffError}
        loading={diffLoading}
        onOpenChange={setDiffOpen}
        open={diffOpen}
      />
    </>
  );
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
