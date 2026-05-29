"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { AlertTriangle, FileText, Pencil, Play, RefreshCw, Route, Square, X } from "lucide-react";
import { toast } from "sonner";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
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
  environment_site_url: string;
  title: string;
  status: string;
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  description: string;
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
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
      yaml_path?: string | null;
      page_type?: string | null;
      status?: string | null;
      blocker_reason?: string | null;
      recent_event?: string | null;
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
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
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
  cancelled: "已中止",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const loginStrategyLabels: Record<string, string> = {
  reuse_state: "复用登录态",
  manual: "手动登录保存状态",
  account_password: "账号密码",
  skip_login: "无需登录",
};

const autoRefreshStatuses = new Set(["queued", "running", "waiting_human", "stopping", "in-progress"]);
const stoppableStatuses = new Set(["queued", "running", "waiting_human"]);
const autoRefreshIntervalMs = 3000;
const explorationPlaceholders = {
  scope: "填写本次要探索的页面范围，例如全站、指定菜单、指定 URL 或核心模块。",
  forbiddenPaths: "填写禁止进入或点击的路径/动作，例如删除、支付、外发、批量通知、退出登录。",
  goal: "填写本次探索要验证的目标，例如遍历元素和链接，检查 401/403、登录跳转和异常页。",
};
const emptyExplorationForm: ExplorationForm = {
  title: "",
  environmentId: "",
  scope: "",
  forbiddenPaths: "",
  description: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};

function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

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
      maxPages: String(run.max_pages ?? 50),
      maxActions: String(run.max_actions ?? 1000),
      timeoutMinutes: String(run.timeout_minutes ?? 120),
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
    const maxPages = parsePositiveInteger(explorationForm.maxPages);
    const maxActions = parsePositiveInteger(explorationForm.maxActions);
    const timeoutMinutes = parsePositiveInteger(explorationForm.timeoutMinutes);
    if (!maxPages || !maxActions || !timeoutMinutes) {
      toast.error("请填写大于 0 的执行边界");
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
          max_pages: maxPages,
          max_actions: maxActions,
          timeout_minutes: timeoutMinutes,
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
  const startLabel = run?.status === "cancelled" ? "重新开始探索" : "开始探索";
  const saveDisabled = !explorationForm.title.trim() || !explorationForm.environmentId || saving;
  const hasNoExplorationArtifacts = detail ? detail.modules.every((module) => hasNoModuleArtifacts(module)) : false;
  const shouldShowNoArtifactNotice = Boolean(
    run && hasNoExplorationArtifacts && (run.status === "cancelled" || run.status === "blocked"),
  );
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
          {canStop ? (
            <Button disabled={stopping} onClick={() => setStopDialogOpen(true)} size="sm" variant="destructive">
              <Square className="size-4" />
              停止探索
            </Button>
          ) : null}
          <Button disabled={startDisabled} onClick={startExploration} size="sm">
            <Play className="size-4" />
            {startLabel}
          </Button>
        </>
      }
      projectScope="project"
      activeTab={activeTab}
      onTabChange={setActiveTab}
      tabs={["探索计划", "探索概览", "探索日志", "探索报告"]}
      title={run?.title ?? "探索任务"}
    >
      {activeTab === "探索概览" && error && failureVisible ? (
        <ExplorationFailureNotice error={error} onClose={() => setFailureVisible(false)} />
      ) : null}

      {activeTab === "探索计划" ? <ExplorationTaskPanel run={run} /> : null}

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
                  <p className="text-muted-foreground text-xs">展示模块、页面进度、最近页面和阻塞说明</p>
                </div>
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
              {loading ? (
                <div className="py-10 text-center text-muted-foreground text-sm">探索任务加载中</div>
              ) : run ? (
                <div className="space-y-3">
                  {shouldShowNoArtifactNotice ? (
                    <NoArtifactNotice run={run} onOpenLog={() => setActiveTab("探索日志")} />
                  ) : null}
                  <ModuleProgressList detail={detail} run={run} />
                </div>
              ) : null}
            </ShellSection>

            <div className="min-w-0">
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
                    label={run?.status === "cancelled" ? "中止探索" : "完成探索"}
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
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>编辑探索任务</DialogTitle>
            <DialogDescription>调整任务名称、关联环境、探索范围、探索目标和禁止路径。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
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
                placeholder={explorationPlaceholders.scope}
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
                placeholder={explorationPlaceholders.forbiddenPaths}
                value={explorationForm.forbiddenPaths}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-description">探索目标</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-description"
                onChange={(event) => setExplorationForm((current) => ({ ...current, description: event.target.value }))}
                placeholder={explorationPlaceholders.goal}
                value={explorationForm.description}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel>执行边界</FieldLabel>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-max-pages">
                  <span className="text-muted-foreground text-xs">页面上限</span>
                  <Input
                    id="exploration-edit-max-pages"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxPages: event.target.value }))
                    }
                    placeholder="50"
                    type="number"
                    value={explorationForm.maxPages}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-max-actions">
                  <span className="text-muted-foreground text-xs">操作上限</span>
                  <Input
                    id="exploration-edit-max-actions"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxActions: event.target.value }))
                    }
                    placeholder="1000"
                    type="number"
                    value={explorationForm.maxActions}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-edit-timeout-minutes">
                  <span className="text-muted-foreground text-xs">超时时间（分钟）</span>
                  <Input
                    id="exploration-edit-timeout-minutes"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, timeoutMinutes: event.target.value }))
                    }
                    placeholder="120"
                    type="number"
                    value={explorationForm.timeoutMinutes}
                  />
                </label>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
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

function ExplorationTaskPanel({ run }: { run: ExplorationRun | null }) {
  const loginStrategy = run ? (loginStrategyLabels[run.login_strategy] ?? run.login_strategy) : "-";

  return (
    <div className="space-y-4">
      <TaskSection title="环境">
        <div className="grid gap-3 md:grid-cols-2">
          <InfoRow label="所属项目" value={displayValue(run?.project_name)} />
          <InfoRow label="测试环境" value={displayValue(run?.environment_name)} />
          <InfoRow label="登录策略" value={loginStrategy} />
          <InfoRow label="站点地址" value={displayValue(run?.environment_site_url)} />
        </div>
      </TaskSection>

      <TaskSection title="探索">
        <InfoRow label="任务名称" value={displayValue(run?.title)} />
        <InfoRow label="探索范围" value={displayValue(run?.scope)} />
        <InfoRow label="禁止路径" value={displayValue(run?.forbidden_paths)} />
        <InfoRow label="探索目标" value={displayValue(run?.description)} />
      </TaskSection>

      <TaskSection title="执行边界">
        <div className="grid gap-3 md:grid-cols-3">
          <InfoRow label="页面上限" value={run ? `${run.max_pages ?? 50} 页` : "-"} />
          <InfoRow label="操作上限" value={run ? `${run.max_actions ?? 1000} 次` : "-"} />
          <InfoRow label="超时时间" value={run ? `${run.timeout_minutes ?? 120} 分钟` : "-"} />
        </div>
      </TaskSection>
    </div>
  );
}

function TaskSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">{children}</CardContent>
    </Card>
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

function NoArtifactNotice({ onOpenLog, run }: { onOpenLog: () => void; run: ExplorationRun }) {
  const isCancelled = run.status === "cancelled";
  const title = isCancelled ? "本次探索已中止，未生成探索产物" : "本次探索被阻塞，未生成探索产物";
  const stopReason =
    run.result_summary || "用户已停止探索；此前任务已无运行中的浏览器探索进程，已生成的日志会继续保留。";
  const description = isCancelled
    ? "此前任务已无运行中的浏览器探索进程，已生成的日志会继续保留；如需重新执行，请使用页面右上角的重新开始探索。"
    : run.result_summary || "当前探索需要人工处理后才能继续，请查看日志确认阻塞原因和证据。";

  return (
    <div className="rounded-lg border bg-muted/20 p-4 text-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="font-medium">{title}</div>
          {isCancelled ? (
            <div className="text-foreground">
              <span className="text-muted-foreground">中止原因：</span>
              {stopReason}
            </div>
          ) : null}
          <p className="text-muted-foreground">{description}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button onClick={onOpenLog} size="sm" type="button" variant="outline">
            查看日志
          </Button>
        </div>
      </div>
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

function hasNoModuleArtifacts(module: ExplorationRunDetail["modules"][number]): boolean {
  return module.pages.length === 0 && module.elements.length === 0 && module.blockers.length === 0;
}

function ModuleProgressList({ detail, run }: { detail: ExplorationRunDetail | null; run: ExplorationRun | null }) {
  if (!run) {
    return null;
  }

  if (!detail) {
    return <div className="py-10 text-center text-muted-foreground text-sm">探索模块进度加载中</div>;
  }

  if (detail.modules.length === 0) {
    return (
      <div className="rounded-lg border bg-muted/20 p-4 text-muted-foreground text-sm">
        暂无模块进度。探索任务执行后会在这里展示模块、页面和阻塞信息。
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {detail.modules.map((module) => {
        const pages = module.pages ?? [];
        const progressLabel = formatModuleProgress(module);
        const progressPercent = formatProgressPercent(module);
        const recentPage = getRecentPage(module);
        const moduleStatusLabel = displayModuleStatus(module.completion_status);

        return (
          <details key={module.id} className="group rounded-lg border bg-background">
            <summary className="flex cursor-pointer list-none items-start gap-3 p-4">
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="min-w-0 font-medium text-sm">{module.module_name || "未命名模块"}</div>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground text-xs">
                    {moduleStatusLabel}
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <InfoRow label="页面进度" value={progressLabel} />
                  <InfoRow label="最近页面" value={recentPage} />
                  <InfoRow
                    label="阻塞说明"
                    value={displayValue(module.completion_summary || getModuleBlockerSummary(module))}
                  />
                  <InfoRow label="进度百分比" value={progressPercent} />
                </div>
              </div>
              <div className="shrink-0 pt-0.5 text-muted-foreground text-xs group-open:rotate-180">⌄</div>
            </summary>
            <div className="border-t px-4 py-3">
              <div className="mb-3 grid gap-2 text-sm sm:grid-cols-2">
                <InfoRow label="模块名称" value={displayValue(module.module_name)} />
                <InfoRow label="状态" value={moduleStatusLabel} />
                <InfoRow label="页面进度" value={progressLabel} />
                <InfoRow label="最近页面" value={recentPage} />
                <InfoRow
                  label="阻塞说明"
                  value={displayValue(module.completion_summary || getModuleBlockerSummary(module))}
                />
                <InfoRow label="进度百分比" value={progressPercent} />
              </div>
              <div className="space-y-2">
                <div className="font-medium text-muted-foreground text-xs">页面详情</div>
                {pages.length > 0 ? (
                  <div className="overflow-hidden rounded-md border">
                    <Table className="table-fixed">
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="w-[190px] px-3 text-muted-foreground">页面标题</TableHead>
                          <TableHead className="w-[140px] px-3 text-muted-foreground">页面类型</TableHead>
                          <TableHead className="w-[120px] px-3 text-muted-foreground">状态</TableHead>
                          <TableHead className="px-3 text-muted-foreground">URL</TableHead>
                          <TableHead className="px-3 text-muted-foreground">阻塞说明</TableHead>
                          <TableHead className="px-3 text-muted-foreground">最近事件</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {pages.map((page) => (
                          <TableRow key={page.id}>
                            <TableCell className="px-3 align-top font-medium">{displayValue(page.title)}</TableCell>
                            <TableCell className="px-3 align-top text-muted-foreground">
                              {displayValue(page.page_type ?? page.yaml_path)}
                            </TableCell>
                            <TableCell className="px-3 align-top">{displayValue(page.status)}</TableCell>
                            <TableCell className="px-3 align-top text-muted-foreground">
                              {displayValue(page.url || page.entry_path || page.yaml_path)}
                            </TableCell>
                            <TableCell className="px-3 align-top text-muted-foreground">
                              {displayValue(page.blocker_reason)}
                            </TableCell>
                            <TableCell className="px-3 align-top text-muted-foreground">
                              {displayValue(page.recent_event)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <div className="rounded-md border bg-muted/20 p-3 text-muted-foreground text-sm">暂无页面详情。</div>
                )}
              </div>
            </div>
          </details>
        );
      })}
    </div>
  );
}

function formatModuleProgress(module: ExplorationRunDetail["modules"][number]): string {
  const explored = module.explored_page_count ?? 0;
  const planned = module.planned_page_count ?? 0;
  if (planned > 0) {
    return `${explored}/${planned} 页`;
  }
  return `${explored} 页`;
}

function formatProgressPercent(module: ExplorationRunDetail["modules"][number]): string {
  const explored = module.explored_page_count ?? 0;
  const planned = module.planned_page_count ?? 0;
  if (planned <= 0) {
    return explored > 0 ? "100%" : "-";
  }
  return `${Math.min(100, Math.round((explored / planned) * 100))}%`;
}

function getRecentPage(module: ExplorationRunDetail["modules"][number]): string {
  const lastPage = module.pages.at(-1);
  return displayValue(lastPage?.title || lastPage?.url || lastPage?.entry_path || lastPage?.yaml_path);
}

function getModuleBlockerSummary(module: ExplorationRunDetail["modules"][number]): string {
  const pageBlocker = module.pages.find((page) => page.blocker_reason?.trim());
  if (pageBlocker?.blocker_reason) {
    return pageBlocker.blocker_reason;
  }
  const blocker = module.blockers.find((item) => item.reason?.trim());
  if (blocker?.reason) {
    return blocker.reason;
  }
  return module.blocked_page_count > 0 ? `${module.blocked_page_count} 个页面阻塞` : "-";
}

function displayModuleStatus(status: string): string {
  return statusLabels[status] ?? (status || "-");
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b pb-3 last:border-b-0 last:pb-0 sm:grid-cols-[96px_1fr]">
      <div className="text-muted-foreground">{label}</div>
      <div className="min-w-0 break-words font-medium">{value}</div>
    </div>
  );
}

function displayValue(value: string | null | undefined): string {
  return value?.trim() || "-";
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
