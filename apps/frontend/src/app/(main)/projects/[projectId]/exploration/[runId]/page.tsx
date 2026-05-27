"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { AlertTriangle, FileText, Pencil, Play, RefreshCw, Route, Square, X } from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { AgentPlan, type AgentPlanTask } from "@/components/ui/agent-plan";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, formatDateTime, parseApiTimestamp } from "@/lib/api-client";

type ExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  title: string;
  status: string;
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  description: string;
  artifact_root: string;
  result_summary: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  available_actions: string[];
};

type ExplorationRunDetail = {
  run: ExplorationRun;
  modules: Array<{
    id: string;
    module_key: string;
    module_name: string;
    entry_path: string;
    planned_page_count: number;
    explored_page_count: number;
    blocked_page_count: number;
    action_count: number;
    field_count: number;
    state_transition_count: number;
    completion_status: string;
    completion_summary: string;
    pages: Array<{
      id: string;
      title: string;
      url: string;
      entry_path: string;
      structure_summary: string;
    }>;
    elements: Array<{
      id: string;
      page_id: string | null;
      element_name: string;
      element_type: string;
      recommended_locator: string;
      stability_note: string;
    }>;
    blockers: Array<{
      id: string;
      page_ref: string;
      reason_type: string;
      reason: string;
      suggested_action: string;
      is_blocking: boolean;
    }>;
  }>;
};

type ExplorationReport = {
  run_id: string;
  version_no: number | null;
  title: string;
  markdown_content: string;
  change_summary: string;
  created_at: string | null;
};

type ExplorationLog = {
  run_id: string;
  log_content: string;
  log_path: string;
  updated_at: string | null;
};

type ProjectEnvironment = {
  id: string;
  project_id: string;
  name: string;
};

type ExplorationForm = {
  title: string;
  environmentId: string;
  scope: string;
  forbiddenPaths: string;
  description: string;
};

type ParsedLogEntry = {
  id: string;
  timestamp: string;
  message: string;
};

const statusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  waiting_human: "等待人工",
  stopping: "正在停止",
  cancelled: "已停止",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const autoRefreshStatuses = new Set(["queued", "running", "waiting_human", "stopping", "in-progress"]);
const stoppableStatuses = new Set(["queued", "running", "waiting_human"]);
const autoRefreshIntervalMs = 3000;
const emptyExplorationForm: ExplorationForm = {
  title: "",
  environmentId: "",
  scope: "",
  forbiddenPaths: "",
  description: "",
};

export default function Page() {
  const params = useParams<{ projectId: string; runId: string }>();
  const projectName = useProjectName(params.projectId);
  const [run, setRun] = useState<ExplorationRun | null>(null);
  const [detail, setDetail] = useState<ExplorationRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const [failureVisible, setFailureVisible] = useState(true);
  const [activeTab, setActiveTab] = useState("探索概览");
  const [report, setReport] = useState<ExplorationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [log, setLog] = useState<ExplorationLog | null>(null);
  const [logLoading, setLogLoading] = useState(false);
  const [logError, setLogError] = useState("");
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [stopDialogOpen, setStopDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [environments, setEnvironments] = useState<ProjectEnvironment[]>([]);
  const [environmentLoading, setEnvironmentLoading] = useState(false);
  const [explorationForm, setExplorationForm] = useState<ExplorationForm>(emptyExplorationForm);

  const loadRun = useCallback(
    async (options?: { silent?: boolean }) => {
      if (!options?.silent) {
        setLoading(true);
      }
      setError("");
      setFailureVisible(true);
      try {
        const data = await apiRequest<ExplorationRunDetail>(
          `/projects/${params.projectId}/exploration-runs/${params.runId}/detail`,
        );
        setDetail(data);
        setRun(data.run);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "探索任务加载失败");
      } finally {
        if (!options?.silent) {
          setLoading(false);
        }
      }
    },
    [params.projectId, params.runId],
  );

  useEffect(() => {
    void loadRun();
  }, [loadRun]);

  useEffect(() => {
    if (!run || !autoRefreshStatuses.has(run.status)) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadRun({ silent: true });
    }, autoRefreshIntervalMs);

    return () => window.clearInterval(timer);
  }, [loadRun, run]);

  const loadReport = useCallback(async () => {
    setReportLoading(true);
    setReportError("");
    try {
      const data = await apiRequest<ExplorationReport>(
        `/projects/${params.projectId}/exploration-runs/${params.runId}/report`,
      );
      setReport(data);
    } catch (requestError) {
      setReportError(requestError instanceof Error ? requestError.message : "探索报告加载失败");
    } finally {
      setReportLoading(false);
    }
  }, [params.projectId, params.runId]);

  useEffect(() => {
    if (activeTab === "探索报告") {
      void loadReport();
    }
  }, [activeTab, loadReport]);

  const loadLog = useCallback(async () => {
    setLogLoading(true);
    setLogError("");
    try {
      const data = await apiRequest<ExplorationLog>(
        `/projects/${params.projectId}/exploration-runs/${params.runId}/log`,
      );
      setLog(data);
    } catch (requestError) {
      setLogError(requestError instanceof Error ? requestError.message : "探索日志加载失败");
    } finally {
      setLogLoading(false);
    }
  }, [params.projectId, params.runId]);

  useEffect(() => {
    if (activeTab === "探索日志") {
      void loadLog();
    }
  }, [activeTab, loadLog]);

  async function startExploration() {
    if (!run) {
      return;
    }
    setStarting(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/start`, {
        method: "POST",
      });
      setRun(updated);
      toast.success("探索任务已开始");
      window.setTimeout(() => void loadRun({ silent: true }), 800);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务启动失败");
    } finally {
      setStarting(false);
    }
  }

  async function stopExploration() {
    if (!run) {
      return;
    }
    setStopping(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/stop`, {
        method: "POST",
      });
      setRun(updated);
      setDetail((current) => (current ? { ...current, run: updated } : current));
      setStopDialogOpen(false);
      toast.success("探索任务已停止");
      window.setTimeout(() => void loadRun({ silent: true }), 800);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务停止失败");
    } finally {
      setStopping(false);
    }
  }

  async function loadEnvironments() {
    setEnvironmentLoading(true);
    try {
      const data = await apiRequest<ProjectEnvironment[]>(`/projects/${params.projectId}/environments`);
      setEnvironments(data);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "环境列表加载失败");
    } finally {
      setEnvironmentLoading(false);
    }
  }

  function openEditDialog() {
    if (!run) {
      return;
    }
    setExplorationForm({
      title: run.title,
      environmentId: run.environment_id,
      scope: run.scope,
      forbiddenPaths: run.forbidden_paths,
      description: run.description,
    });
    setEditDialogOpen(true);
    if (environments.length === 0) {
      void loadEnvironments();
    }
  }

  async function saveExplorationRun() {
    if (!run) {
      return;
    }
    if (!explorationForm.title.trim() || !explorationForm.environmentId) {
      toast.error("请填写任务名称并选择环境");
      return;
    }

    setSaving(true);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          environment_id: explorationForm.environmentId,
          title: explorationForm.title,
          scope: explorationForm.scope,
          forbidden_paths: explorationForm.forbiddenPaths,
          description: explorationForm.description,
        }),
      });
      setRun(updated);
      setDetail((current) => (current ? { ...current, run: updated } : current));
      setEditDialogOpen(false);
      toast.success("探索任务已更新");
      void loadRun({ silent: true });
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务更新失败");
    } finally {
      setSaving(false);
    }
  }

  const canStart = run ? ["pending", "partial", "completed", "blocked", "cancelled"].includes(run.status) : false;
  const canStop = run ? stoppableStatuses.has(run.status) : false;
  const canEdit = run ? !["queued", "running", "waiting_human", "stopping"].includes(run.status) : false;
  const startDisabled = !canStart || starting;
  const saveDisabled = !explorationForm.title.trim() || !explorationForm.environmentId || saving;
  const planTasks = detail ? toPlanTasks(detail) : [];
  const explorationDuration = run ? formatExplorationDuration(run) : "-";
  const failureDetail = error
    ? {
        error,
        projectId: params.projectId,
        requestPath: `/projects/${params.projectId}/exploration-runs/${params.runId}/detail`,
        runId: params.runId,
        failedAt: formatDateTime(new Date().toISOString()),
      }
    : null;

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "探索", run?.title ?? "探索任务"]}
      description="查看探索任务运行概览、执行日志和探索报告。"
      tabActions={
        <>
          <Button disabled={loading} onClick={() => void loadRun()} size="sm" variant="outline">
            <RefreshCw className="size-4" />
            刷新
          </Button>
          <Button disabled={!canEdit} onClick={openEditDialog} size="sm" variant="outline">
            <Pencil className="size-4" />
            编辑
          </Button>
          <Button
            disabled={!canStop || stopping}
            onClick={() => setStopDialogOpen(true)}
            size="sm"
            variant="destructive"
          >
            <Square className="size-4" />
            停止探索
          </Button>
          <Button disabled={startDisabled} onClick={startExploration} size="sm">
            <Play className="size-4" />
            开始探索
          </Button>
        </>
      }
      projectScope="project"
      activeTab={activeTab}
      onTabChange={setActiveTab}
      tabs={["探索概览", "探索日志", "探索报告"]}
      title={run?.title ?? "探索任务"}
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}

      {activeTab === "探索概览" ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              helper="当前探索任务状态"
              icon={Route}
              label="任务状态"
              value={run ? (statusLabels[run.status] ?? run.status) : "-"}
            />
            <MetricCard
              helper="用于页面访问和探索执行"
              icon={Play}
              label="测试环境"
              value={run?.environment_name ?? "-"}
            />
            <MetricCard
              helper="最近一次状态变更"
              icon={RefreshCw}
              label="更新时间"
              value={run ? formatDateTime(run.updated_at) : "-"}
            />
            <MetricCard helper="从开始探索到结束的耗时" icon={FileText} label="探索时长" value={explorationDuration} />
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
            <ShellSection className="min-w-0">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-medium text-sm">探索模块进度</h2>
                  <p className="text-muted-foreground text-xs">展示当前模块、子页面、元素和阻塞项探索状态</p>
                </div>
                {run ? (
                  <div className="flex items-center gap-2">
                    <Badge variant={run.status === "blocked" ? "destructive" : "secondary"}>
                      {statusLabels[run.status] ?? run.status}
                    </Badge>
                    {canStop ? (
                      <Button
                        disabled={stopping}
                        onClick={() => setStopDialogOpen(true)}
                        size="sm"
                        type="button"
                        variant="destructive"
                      >
                        <Square className="size-3.5" />
                        停止
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
              {loading ? (
                <div className="py-10 text-center text-muted-foreground text-sm">探索任务加载中</div>
              ) : run ? (
                <AgentPlan
                  className="max-w-full"
                  defaultExpandedTaskIds={planTasks.map((task) => task.id)}
                  tasks={planTasks}
                />
              ) : null}
            </ShellSection>

            <div className="min-w-0 space-y-4">
              <Card size="sm">
                <CardHeader>
                  <CardTitle className="text-sm">输入摘要</CardTitle>
                  <CardDescription>本次探索的环境和范围</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <InfoRow label="关联环境" value={run?.environment_name ?? "-"} />
                  <InfoRow label="探索范围" value={run?.scope || "-"} />
                  <InfoRow label="禁止路径" value={run?.forbidden_paths || "-"} />
                </CardContent>
              </Card>

              <Card size="sm">
                <CardHeader>
                  <CardTitle className="text-sm">执行时间线</CardTitle>
                  <CardDescription>按北京时间展示关键阶段</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <TimelineItem
                    active={Boolean(run)}
                    label="创建任务"
                    value={run ? formatDateTime(run.created_at) : "-"}
                  />
                  <TimelineItem
                    active={Boolean(run?.started_at)}
                    label="开始探索"
                    value={run?.started_at ? formatDateTime(run.started_at) : "待执行"}
                  />
                  <TimelineItem
                    active={Boolean(run?.finished_at)}
                    label="完成探索"
                    value={run?.finished_at ? formatDateTime(run.finished_at) : "等待结果"}
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      ) : null}

      {activeTab === "探索日志" ? (
        <ExplorationLogPanel
          error={logError}
          failureDetail={failureDetail}
          loading={logLoading}
          log={log}
          run={run}
          onReload={() => void loadLog()}
        />
      ) : null}

      {activeTab === "探索报告" ? (
        <ExplorationReportPanel
          error={reportError}
          loading={reportLoading}
          report={report}
          onReload={() => void loadReport()}
        />
      ) : null}

      <Dialog onOpenChange={setEditDialogOpen} open={editDialogOpen}>
        <DialogContent className="gap-6 p-6 sm:max-w-3xl">
          <DialogHeader className="gap-3">
            <DialogTitle>编辑探索任务</DialogTitle>
            <DialogDescription>调整任务名称、关联环境、探索范围、禁止路径和任务说明。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="exploration-title">任务名称</FieldLabel>
              <Input
                id="exploration-title"
                onChange={(event) => setExplorationForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="后台管理系统全站探索"
                value={explorationForm.title}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="exploration-environment">环境</FieldLabel>
              <Select
                disabled={environmentLoading}
                onValueChange={(value) => setExplorationForm((current) => ({ ...current, environmentId: value }))}
                value={explorationForm.environmentId}
              >
                <SelectTrigger className="w-full" id="exploration-environment">
                  <SelectValue placeholder={environmentLoading ? "环境加载中" : "选择环境"} />
                </SelectTrigger>
                <SelectContent>
                  {environments.map((environment) => (
                    <SelectItem key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-scope">探索范围</FieldLabel>
              <Textarea
                className="min-h-24"
                id="exploration-scope"
                onChange={(event) => setExplorationForm((current) => ({ ...current, scope: event.target.value }))}
                placeholder="菜单范围、URL 白名单、核心模块标记"
                value={explorationForm.scope}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-forbidden-paths">禁止路径</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-forbidden-paths"
                onChange={(event) =>
                  setExplorationForm((current) => ({ ...current, forbiddenPaths: event.target.value }))
                }
                placeholder="删除、支付、外发、批量通知等危险路径"
                value={explorationForm.forbiddenPaths}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-description">描述</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-description"
                onChange={(event) => setExplorationForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="本次探索目标、角色说明、验证码处理方式或人工注意事项"
                value={explorationForm.description}
              />
            </Field>
          </FieldGroup>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setEditDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={saveDisabled} onClick={saveExplorationRun} type="button">
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={setStopDialogOpen} open={stopDialogOpen}>
        <DialogContent className="gap-5 p-6 sm:max-w-md">
          <DialogHeader className="gap-3">
            <DialogTitle>停止探索任务</DialogTitle>
            <DialogDescription>停止后将终止当前浏览器探索进程，已生成的截图、日志和页面事实会保留。</DialogDescription>
          </DialogHeader>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setStopDialogOpen(false)} type="button" variant="outline">
              继续探索
            </Button>
            <Button disabled={stopping} onClick={stopExploration} type="button" variant="destructive">
              <Square className="size-4" />
              停止探索
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function ExplorationFailureNotice({ error, onClose }: { error: string; onClose: () => void }) {
  return (
    <div className="flex min-h-10 items-center gap-2 rounded-lg border border-destructive/35 bg-destructive/8 px-3 text-sm shadow-sm">
      <AlertTriangle className="size-4 shrink-0 text-destructive" />
      <div className="min-w-0 flex-1 truncate text-destructive">
        探索任务加载失败：{error}，详细信息请查看“探索日志”。
      </div>
      <Button aria-label="关闭探索失败信息" onClick={onClose} size="icon-xs" type="button" variant="ghost">
        <X className="size-4" />
      </Button>
    </div>
  );
}

function ExplorationLogPanel({
  error,
  failureDetail,
  loading,
  log,
  onReload,
  run,
}: {
  error: string;
  failureDetail: {
    error: string;
    projectId: string;
    requestPath: string;
    runId: string;
    failedAt: string;
  } | null;
  loading: boolean;
  log: ExplorationLog | null;
  onReload: () => void;
  run: ExplorationRun | null;
}) {
  const entries = parseLogEntries(log?.log_content ?? "");

  return (
    <ShellSection>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-sm">探索日志</h2>
          <p className="text-muted-foreground text-xs">按时间条目展示探索任务加载、执行和失败诊断信息</p>
        </div>
        <Button disabled={loading} onClick={onReload} size="sm" type="button" variant="outline">
          <RefreshCw className="size-4" />
          刷新日志
        </Button>
      </div>

      {failureDetail ? (
        <div className="space-y-3 rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-sm">
          <div className="flex items-center gap-2 font-medium text-destructive">
            <AlertTriangle className="size-4" />
            探索任务加载失败
          </div>
          <div className="grid gap-2">
            <InfoRow label="失败原因" value={failureDetail.error} />
            <InfoRow label="项目 ID" value={failureDetail.projectId} />
            <InfoRow label="请求接口" value={failureDetail.requestPath} />
            <InfoRow label="失败时间" value={failureDetail.failedAt} />
            <InfoRow label="建议操作" value="检查后端服务、网络连接和当前账号权限后点击刷新重试。" />
          </div>
        </div>
      ) : loading ? (
        <div className="py-10 text-center text-muted-foreground text-sm">探索日志加载中</div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-destructive text-sm">
          探索日志加载失败：{error}
        </div>
      ) : entries.length > 0 ? (
        <div className="overflow-hidden rounded-lg border bg-background">
          <div className="grid gap-2 border-b bg-muted/25 px-4 py-3 text-muted-foreground text-xs sm:grid-cols-[1fr_auto]">
            <span className="truncate">{log?.log_path || "探索执行日志"}</span>
            <span>{entries.length} 条</span>
          </div>
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[190px] px-4 text-muted-foreground">时间</TableHead>
                <TableHead className="px-4 text-muted-foreground">日志内容</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="px-4 align-top font-mono text-muted-foreground text-xs leading-6">
                    <time>{entry.timestamp}</time>
                  </TableCell>
                  <TableCell className="min-w-0 px-4 align-top">
                    <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-6">
                      {entry.message}
                    </pre>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : log?.log_content ? (
        <div className="rounded-lg border bg-background p-4">
          <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-6">{log.log_content}</pre>
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
          暂无失败日志。
          {run?.result_summary ? `最近执行摘要：${run.result_summary}` : "任务执行后会在这里展示日志信息。"}
        </div>
      )}
    </ShellSection>
  );
}

function ExplorationReportPanel({
  error,
  loading,
  report,
  onReload,
}: {
  error: string;
  loading: boolean;
  report: ExplorationReport | null;
  onReload: () => void;
}) {
  return (
    <ShellSection>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-sm">探索报告</h2>
          <p className="text-muted-foreground text-xs">展示探索任务生成的 Markdown 报告</p>
        </div>
        <Button disabled={loading} onClick={onReload} size="sm" type="button" variant="outline">
          <RefreshCw className="size-4" />
          刷新报告
        </Button>
      </div>

      {loading ? (
        <div className="py-10 text-center text-muted-foreground text-sm">探索报告加载中</div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/25 bg-destructive/5 p-4 text-destructive text-sm">
          探索报告加载失败：{error}
        </div>
      ) : report?.markdown_content ? (
        <div className="space-y-3">
          <div className="grid gap-2 rounded-lg border bg-muted/20 p-3 text-sm sm:grid-cols-3">
            <InfoRow label="报告版本" value={report.version_no ? `v${report.version_no}` : "-"} />
            <InfoRow label="生成时间" value={report.created_at ? formatDateTime(report.created_at) : "-"} />
            <InfoRow label="变更摘要" value={report.change_summary || "-"} />
          </div>
          <MarkdownPreview
            className="rounded-lg border bg-background p-4"
            content={report.markdown_content}
            emptyText="当前探索报告暂无可展示内容。"
          />
        </div>
      ) : (
        <div className="rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
          暂无探索报告。探索任务完成后会在这里展示 Markdown 格式报告。
        </div>
      )}
    </ShellSection>
  );
}

function parseLogEntries(content: string): ParsedLogEntry[] {
  const lines = content.split(/\r?\n/).filter((line) => line.trim().length > 0);
  const entries: ParsedLogEntry[] = [];
  const timePrefixPattern =
    /^(\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)?|\d{2}:\d{2}:\d{2}(?:[.,]\d{3,6})?)(?:\s*[|:-]\s*|\s+)(.*)$/;

  for (const line of lines) {
    const matched = line.match(timePrefixPattern);
    if (matched) {
      entries.push({
        id: `log-${entries.length}`,
        timestamp: matched[1],
        message: matched[2]?.trim() || line.trim(),
      });
      continue;
    }

    const lastEntry = entries.at(-1);
    if (lastEntry) {
      lastEntry.message = `${lastEntry.message}\n${line}`;
    }
  }

  return entries;
}

function formatExplorationDuration(run: ExplorationRun): string {
  if (!run.started_at) {
    return "-";
  }

  const startedAt = parseApiTimestamp(run.started_at);
  const finishedAt = run.finished_at ? parseApiTimestamp(run.finished_at) : Date.now();
  if (!Number.isFinite(startedAt) || !Number.isFinite(finishedAt) || finishedAt < startedAt) {
    return "-";
  }

  const totalSeconds = Math.floor((finishedAt - startedAt) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

function toPlanTasks(detail: ExplorationRunDetail): AgentPlanTask[] {
  return detail.modules.map((module) => {
    const pageSubtasks = module.pages.map((page) => ({
      id: `page-${page.id}`,
      title: page.title || page.url || page.entry_path || "未命名页面",
      description: page.structure_summary || page.url || "页面已纳入探索结果。",
      status: "completed" as const,
      meta: [page.url || page.entry_path].filter(Boolean),
    }));
    const blockerSubtasks = module.blockers.map((blocker) => ({
      id: `blocker-${blocker.id}`,
      title: blocker.page_ref || blocker.reason_type || "探索阻塞项",
      description: [blocker.reason, blocker.suggested_action].filter(Boolean).join(" 建议："),
      status: blocker.is_blocking ? ("blocked" as const) : ("partial" as const),
      meta: [blocker.reason_type].filter(Boolean),
    }));
    const elementSubtasks = module.elements.slice(0, 6).map((element) => ({
      id: `element-${element.id}`,
      title: element.element_name,
      description: element.stability_note || element.recommended_locator || "已识别页面元素。",
      status: "completed" as const,
      meta: [element.element_type, element.recommended_locator].filter(Boolean),
    }));
    const pendingSubtask =
      pageSubtasks.length + blockerSubtasks.length + elementSubtasks.length === 0
        ? [
            {
              id: `pending-${module.id}`,
              title: "等待探索产物",
              description: "开始探索后会在这里展示模块子页面、关键元素、阻塞项和完成情况。",
              status: normalizePlanStatus(detail.run.status),
              meta: [module.entry_path].filter(Boolean),
            },
          ]
        : [];

    return {
      id: module.id,
      title: module.module_name,
      description: module.completion_summary || module.entry_path,
      status: normalizePlanStatus(module.completion_status),
      dependencies: [
        formatModulePageProgress(module),
        module.blocked_page_count ? `${module.blocked_page_count} 阻塞` : "",
      ].filter(Boolean),
      meta: [module.entry_path].filter(Boolean),
      subtasks: [...pageSubtasks, ...blockerSubtasks, ...elementSubtasks, ...pendingSubtask],
    };
  });
}

function formatModulePageProgress(module: ExplorationRunDetail["modules"][number]): string {
  if (module.planned_page_count > 0 && module.completion_status === "completed") {
    return `${module.explored_page_count}/${module.planned_page_count} 页面`;
  }
  if (module.planned_page_count > 0) {
    return `已探索 ${module.explored_page_count}/${module.planned_page_count} 页`;
  }
  return `已探索 ${module.explored_page_count} 页`;
}

function normalizePlanStatus(status: string): AgentPlanTask["status"] {
  if (status === "running" || status === "in-progress") {
    return "in-progress";
  }
  if (status === "queued") {
    return "queued";
  }
  if (status === "pending") {
    return "pending";
  }
  if (status === "completed" || status === "partial" || status === "blocked" || status === "failed") {
    return status;
  }
  return "pending";
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[96px_1fr]">
      <div className="text-muted-foreground">{label}</div>
      <div className="min-w-0 break-words font-medium">{value}</div>
    </div>
  );
}

function TimelineItem({ active, label, value }: { active: boolean; label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div
          className={active ? "mt-1 size-2 rounded-full bg-primary" : "mt-1 size-2 rounded-full bg-muted-foreground/30"}
        />
        <div className="mt-1 h-8 w-px bg-border" />
      </div>
      <div className="min-w-0">
        <div className="font-medium">{label}</div>
        <div className="text-muted-foreground text-xs">{value}</div>
      </div>
    </div>
  );
}
