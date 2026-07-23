"use client";

import { useCallback, useEffect, useState } from "react";

import { Bot, Check, Loader2, RefreshCw, X } from "lucide-react";
import { toast } from "sonner";

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
  type ApiAutomationRun,
  type ApiRepairSession,
  applyApiRepairAttempt,
  approveApiRepairAttempt,
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
  const recommendations = (attempt?.diagnosis?.issues ?? [])
    .map((issue) => issue.recommendation?.trim())
    .filter((recommendation): recommendation is string => Boolean(recommendation));
  const summary = attempt?.validation?.summary ?? {};
  const passed = summary.passed ?? 0;
  const failed = summary.failed ?? 0;

  return (
    <>
      <Drawer direction="right" onOpenChange={onOpenChange} open={open}>
        <DrawerContent className="h-full w-full data-[vaul-drawer-direction=right]:sm:max-w-3xl">
          <DrawerHeader className="border-b pr-14">
            <div className="flex flex-wrap items-center gap-2">
              <Bot className="size-5 text-blue-600" />
              <DrawerTitle>接口自动化 AI 分析与修复</DrawerTitle>
              {attempt ? <Badge variant="outline">第 {attempt.attempt_number} 轮</Badge> : null}
              {attempt ? <Badge variant="secondary">{apiRepairStatusLabel(attempt.status)}</Badge> : null}
            </div>
            <DrawerDescription>运行 {run.id} · 确认后生成候选修改，验证通过后再应用正式测试代码</DrawerDescription>
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

                {attempt.error_message ? (
                  <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
                    {attempt.error_message}
                  </div>
                ) : null}

                {attempt.diagnosis?.summary ? (
                  <section className="space-y-3">
                    <h3 className="font-semibold text-sm">诊断结果</h3>
                    <p className="whitespace-pre-wrap text-muted-foreground text-sm leading-6">
                      {attempt.diagnosis.summary}
                    </p>
                  </section>
                ) : null}

                {proposal?.script_repair_allowed ? (
                  <section className="space-y-3 rounded-xl border bg-muted/20 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-sm">确认修改代码</h3>
                      <Badge variant="outline">置信度 {Math.round(proposal.confidence * 100)}%</Badge>
                    </div>
                    <p className="font-medium text-sm">{proposal.title}</p>
                    <p className="whitespace-pre-wrap text-muted-foreground text-sm leading-6">{proposal.summary}</p>
                    {proposal.proposed_changes.length ? (
                      <div className="space-y-1 text-sm">
                        <div className="font-medium">拟修改代码</div>
                        {proposal.proposed_changes.map((item) => (
                          <p className="text-muted-foreground" key={item}>
                            • {item}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ) : null}

                {attempt.status === "proposal_ready" && !proposal ? (
                  <section className="space-y-3 rounded-xl border bg-muted/20 p-4">
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
                            • {recommendation}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </section>
                ) : null}

                {attempt.validation?.summary ? (
                  <section className="space-y-3">
                    <h3 className="font-semibold text-sm">验证结果</h3>
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

          <DrawerFooter className="flex-row flex-wrap justify-end border-t">
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
                    确认修改代码
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
              <div className="flex items-center px-2 text-muted-foreground text-sm">
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
