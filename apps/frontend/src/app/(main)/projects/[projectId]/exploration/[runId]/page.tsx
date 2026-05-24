"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ArrowLeft, FileText, Play, RefreshCw, Route, Terminal } from "lucide-react";
import { toast } from "sonner";

import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useProjectName } from "@/components/ai-testing/use-project-name";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiRequest, formatDateTime } from "@/lib/api-client";

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

const statusLabels: Record<string, string> = {
  queued: "排队中",
  running: "探索中",
  waiting_human: "等待人工",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const loginStrategyLabels: Record<string, string> = {
  reuse_state: "复用登录态",
  manual: "手动登录保存状态",
  account_password: "账号密码",
  skip_login: "跳过登录",
};

export default function Page() {
  const params = useParams<{ projectId: string; runId: string }>();
  const router = useRouter();
  const projectName = useProjectName(params.projectId);
  const [run, setRun] = useState<ExplorationRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const loadRun = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<ExplorationRun>(`/projects/${params.projectId}/exploration-runs/${params.runId}`);
      setRun(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "探索任务加载失败");
    } finally {
      setLoading(false);
    }
  }, [params.projectId, params.runId]);

  useEffect(() => {
    void loadRun();
  }, [loadRun]);

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
      window.setTimeout(() => void loadRun(), 800);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务启动失败");
    } finally {
      setStarting(false);
    }
  }

  const canStart = run ? !["running", "waiting_human"].includes(run.status) : false;

  return (
    <PageShell
      breadcrumbs={["项目", projectName, "探索", run?.title ?? "探索任务"]}
      description="查看探索任务运行状态、输入摘要、执行日志和产物。"
      primaryAction={canStart ? "开始探索" : undefined}
      onPrimaryAction={canStart ? startExploration : undefined}
      projectScope="project"
      activeTab="运行详情"
      tabs={[{ label: "探索任务", href: `/projects/${params.projectId}/exploration` }, "运行详情", "日志", "产物"]}
      title={run?.title ?? "探索任务"}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => router.push(`/projects/${params.projectId}/exploration`)} size="sm" variant="outline">
          <ArrowLeft className="size-4" />
          返回列表
        </Button>
        <Button disabled={loading} onClick={() => void loadRun()} size="sm" variant="outline">
          <RefreshCw className="size-4" />
          刷新
        </Button>
        {canStart ? (
          <Button disabled={starting} onClick={startExploration} size="sm">
            <Play className="size-4" />
            开始探索
          </Button>
        ) : null}
      </div>

      {error ? (
        <ShellSection>
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
            {error}
          </div>
        </ShellSection>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          helper="当前探索任务状态"
          icon={Route}
          label="任务状态"
          value={run ? (statusLabels[run.status] ?? run.status) : "-"}
        />
        <MetricCard
          helper="用于登录和页面访问"
          icon={Play}
          label="登录策略"
          value={run ? (loginStrategyLabels[run.login_strategy] ?? run.login_strategy) : "-"}
        />
        <MetricCard
          helper="最近一次状态变更"
          icon={RefreshCw}
          label="更新时间"
          value={run ? formatDateTime(run.updated_at) : "-"}
        />
        <MetricCard
          helper="探索结果文件目录"
          icon={FileText}
          label="产物目录"
          value={run?.artifact_root ? "已生成" : "-"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <ShellSection>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">运行详情</h2>
              <p className="text-muted-foreground text-xs">探索执行状态和输入摘要</p>
            </div>
            {run ? (
              <Badge variant={run.status === "blocked" ? "destructive" : "secondary"}>
                {statusLabels[run.status] ?? run.status}
              </Badge>
            ) : null}
          </div>
          {loading ? (
            <div className="py-10 text-center text-muted-foreground text-sm">探索任务加载中</div>
          ) : run ? (
            <div className="space-y-4 text-sm">
              <InfoRow label="任务 ID" value={run.id} />
              <InfoRow label="关联环境" value={run.environment_name} />
              <InfoRow label="探索范围" value={run.scope || "-"} />
              <InfoRow label="禁止路径" value={run.forbidden_paths || "-"} />
              <InfoRow label="任务说明" value={run.description || "-"} />
              <InfoRow label="执行摘要" value={run.result_summary || "尚未开始执行。"} />
              <InfoRow label="创建时间" value={formatDateTime(run.created_at)} />
              <InfoRow label="开始时间" value={run.started_at ? formatDateTime(run.started_at) : "-"} />
              <InfoRow label="结束时间" value={run.finished_at ? formatDateTime(run.finished_at) : "-"} />
            </div>
          ) : null}
        </ShellSection>

        <div className="space-y-4">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="text-sm">执行时间线</CardTitle>
              <CardDescription>第一版展示关键阶段</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <TimelineItem
                active={Boolean(run)}
                label="任务已创建"
                value={run ? formatDateTime(run.created_at) : "-"}
              />
              <TimelineItem
                active={Boolean(run?.started_at)}
                label="开始探索"
                value={run?.started_at ? formatDateTime(run.started_at) : "待执行"}
              />
              <TimelineItem
                active={Boolean(run?.finished_at)}
                label="探索结束"
                value={run?.finished_at ? formatDateTime(run.finished_at) : "等待结果"}
              />
            </CardContent>
          </Card>

          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Terminal className="size-4" />
                产物
              </CardTitle>
              <CardDescription>探索文档、JSON 和日志会写入后端文件系统</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <InfoRow label="产物根目录" value={run?.artifact_root || "-"} />
              <Separator />
              <p className="text-muted-foreground text-xs">
                深度页面、日志和文档预览接口后续接入；当前先展示运行入口和产物路径。
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageShell>
  );
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
