"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpenText,
  CalendarDays,
  ClipboardCheck,
  Clock3,
  FileSearch,
  FileText,
  Gauge,
  History,
  type LucideIcon,
  PlaySquare,
  Tags,
  TestTubeDiagonal,
} from "lucide-react";

import { AssetTrendChart } from "@/app/(main)/dashboard/_components/asset-trend-chart";
import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type ApiDashboardOverview,
  type ApiProject,
  type ApiRequirementDocument,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { useProjectContextStore } from "@/stores/project-context-store";

const statusToLabel = (status: ApiProject["status"]) => (status === "archived" ? "已归档" : "进行中");

type WorkspaceEntry = {
  title: string;
  description: string;
  path: string;
  icon: LucideIcon;
  primary?: boolean;
};

export default function Page() {
  const router = useRouter();
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const selectProject = useProjectContextStore((state) => state.selectProject);
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [project, setProject] = useState<ApiProject | null>(null);
  const [overview, setOverview] = useState<ApiDashboardOverview | null>(null);
  const [requirementCount, setRequirementCount] = useState<number | null>(null);
  const [trendDays, setTrendDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const loadProject = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [projects, requirements] = await Promise.all([
        apiRequest<ApiProject[]>("/projects"),
        apiRequest<ApiRequirementDocument[]>(`/projects/${projectId}/requirements`),
      ]);
      setProject(projects.find((item) => item.id === projectId) ?? null);
      setRequirementCount(requirements.length);
    } catch (requestError) {
      setProject(null);
      setRequirementCount(null);
      setError(requestError instanceof Error ? requestError.message : "项目概览加载失败");
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const loadOverview = useCallback(async () => {
    setTrendLoading(true);
    try {
      const projectOverview = await apiRequest<ApiDashboardOverview>(
        `/dashboard/overview?project_id=${projectId}&days=${trendDays}`,
      );
      setOverview(projectOverview);
    } catch (requestError) {
      setOverview(null);
      setError(requestError instanceof Error ? requestError.message : "项目趋势加载失败");
    } finally {
      setTrendLoading(false);
    }
  }, [projectId, trendDays]);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  function goToModule(path: string) {
    selectProject(projectId);
    router.push(path);
  }

  const metricByLabel = useMemo(
    () => new Map((overview?.metrics ?? []).map((metric) => [metric.label, metric])),
    [overview],
  );
  const projectName = project?.name ?? overview?.project_name ?? "项目";
  const caseAssetMetric = metricByLabel.get("用例资产数");
  const adoptionMetric = metricByLabel.get("测试用例采纳率");
  const automationMetric = metricByLabel.get("自动化用例数量");
  const workspaceEntries: WorkspaceEntry[] = [
    {
      title: "需求管理",
      description: "维护需求文档、版本与测试点",
      path: "/requirements",
      icon: FileText,
      primary: true,
    },
    {
      title: "探索分析",
      description: "从业务材料梳理场景和风险",
      path: "/exploration",
      icon: FileSearch,
    },
    {
      title: "测试用例",
      description: "查看已生成和采纳的用例资产",
      path: "/test-cases",
      icon: ClipboardCheck,
    },
    {
      title: "UI 自动化",
      description: "管理页面资产与自动化执行记录",
      path: "/automation/ui",
      icon: PlaySquare,
    },
    {
      title: "接口自动化",
      description: "维护接口场景、用例与运行结果",
      path: `/projects/${projectId}/automation/api`,
      icon: TestTubeDiagonal,
    },
    {
      title: "操作日志",
      description: "追踪项目内的关键操作记录",
      path: `/projects/${projectId}/logs`,
      icon: History,
    },
  ];

  return (
    <PageShell
      tabActions={
        <Button onClick={() => goToModule("/requirements")}>
          打开需求工作区
          <ArrowRight className="size-4" />
        </Button>
      }
      activeTab="项目概览"
      breadcrumbs={moduleBreadcrumbs("projects", { label: projectName })}
      projectScope="project"
      tabs={[
        { label: "项目概览", href: `/projects/${projectId}` },
        { label: "版本管理", href: `/projects/${projectId}/versions` },
      ]}
      title={projectName}
    >
      {error ? (
        <OverviewError message={error} onRetry={() => void Promise.all([loadProject(), loadOverview()])} />
      ) : null}
      {loading ? (
        <OverviewSkeleton />
      ) : (
        <>
          <ProjectSummary project={project} />

          <section aria-labelledby="project-metrics-heading" className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-base" id="project-metrics-heading">
                  质量资产
                </h2>
                <p className="text-muted-foreground text-xs">聚合当前项目的需求、用例和自动化建设情况。</p>
              </div>
              <span className="text-muted-foreground text-xs">实时统计</span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                helper={requirementCount === null ? "需求文档加载中" : `已沉淀 ${requirementCount} 份需求文档`}
                icon={FileText}
                label="需求文档"
                value={requirementCount === null ? "-" : String(requirementCount)}
              />
              <MetricCard
                helper={caseAssetMetric?.helper ?? "已采纳 - 条"}
                icon={ClipboardCheck}
                label="用例资产"
                value={caseAssetMetric?.value ?? "-"}
              />
              <MetricCard
                helper={adoptionMetric?.helper ?? "较上周 -"}
                icon={Gauge}
                label="用例采纳率"
                value={adoptionMetric?.value ?? "-"}
              />
              <MetricCard
                helper={automationMetric?.helper ?? "用例数量 - 条"}
                icon={PlaySquare}
                label="自动化用例"
                value={automationMetric?.value ?? "-"}
              />
            </div>
          </section>

          <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(19rem,0.75fr)]">
            <div className="min-w-0">
              {trendLoading ? (
                <Skeleton className="h-[26rem] w-full rounded-xl" />
              ) : overview ? (
                <AssetTrendChart
                  data={overview.trend}
                  days={trendDays}
                  onDaysChange={setTrendDays}
                  projectLabel={projectName}
                />
              ) : null}
            </div>
            <ProjectFacts project={project} projectId={projectId} />
          </div>

          <ShellSection className="gap-4 p-0">
            <div className="flex flex-col gap-1 border-b px-5 py-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="font-semibold text-base">项目工作区</h2>
                <p className="text-muted-foreground text-xs">继续当前项目的需求分析、测试设计和自动化工作。</p>
              </div>
              <span className="text-muted-foreground text-xs">{workspaceEntries.length} 个可用入口</span>
            </div>
            <div className="grid gap-px overflow-hidden bg-border md:grid-cols-2 xl:grid-cols-3">
              {workspaceEntries.map((entry) => (
                <WorkspaceLink entry={entry} key={entry.title} onClick={() => goToModule(entry.path)} />
              ))}
            </div>
          </ShellSection>
        </>
      )}
    </PageShell>
  );
}

function ProjectSummary({ project }: { project: ApiProject | null }) {
  return (
    <section className="relative overflow-hidden rounded-xl border bg-card px-5 py-5 sm:px-6 sm:py-6">
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="rounded-md" variant={project?.status === "archived" ? "secondary" : "default"}>
              <Activity className="size-3" />
              {project ? statusToLabel(project.status) : "状态未知"}
            </Badge>
            <span className="text-muted-foreground text-xs">
              当前版本 {project?.current_version?.version ?? "未设置"}
            </span>
          </div>
          <div>
            <p className="text-balance font-medium text-lg leading-7">
              {project?.description || "当前项目还没有填写说明。"}
            </p>
            <p className="mt-2 max-w-2xl text-muted-foreground text-sm leading-6">
              从需求材料进入测试分析流程，并在同一项目范围内持续沉淀用例、自动化资产和执行记录。
            </p>
          </div>
        </div>
        <div className="grid min-w-64 grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <SummaryFact icon={CalendarDays} label="创建时间" value={formatDateTime(project?.created_at ?? null)} />
          <SummaryFact icon={Clock3} label="最近更新" value={formatDateTime(project?.updated_at ?? null)} />
        </div>
      </div>
    </section>
  );
}

function SummaryFact({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="min-w-0">
      <span className="flex items-center gap-1.5 text-muted-foreground text-xs">
        <Icon className="size-3.5" />
        {label}
      </span>
      <span className="mt-1 block truncate font-medium text-xs tabular-nums">{value}</span>
    </div>
  );
}

function ProjectFacts({ project, projectId }: { project: ApiProject | null; projectId: string }) {
  const facts = [
    { label: "项目名称", value: project?.name ?? "-" },
    { label: "项目状态", value: project ? statusToLabel(project.status) : "-" },
    { label: "当前版本", value: project?.current_version?.version ?? "未设置" },
    { label: "版本名称", value: project?.current_version?.name || "-" },
    { label: "创建时间", value: formatDateTime(project?.created_at ?? null) },
    { label: "最近更新", value: formatDateTime(project?.updated_at ?? null) },
  ];

  return (
    <ShellSection className="p-0">
      <div className="flex items-center justify-between border-b px-5 py-4">
        <div>
          <h2 className="font-semibold text-base">项目资料</h2>
          <p className="text-muted-foreground text-xs">当前项目的基础信息与版本状态。</p>
        </div>
        <BookOpenText className="size-4 text-muted-foreground" />
      </div>
      <dl className="divide-y px-5">
        {facts.map((fact) => (
          <div className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3 py-3.5 text-sm" key={fact.label}>
            <dt className="text-muted-foreground">{fact.label}</dt>
            <dd className="min-w-0 truncate text-right font-medium tabular-nums">{fact.value}</dd>
          </div>
        ))}
      </dl>
      <div className="grid grid-cols-2 gap-2 border-t p-3">
        <Button asChild variant="outline">
          <Link href={`/projects/${projectId}/versions`}>
            <Tags className="size-4" />
            版本管理
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link href={`/projects/${projectId}/logs`}>
            <History className="size-4" />
            项目日志
          </Link>
        </Button>
      </div>
    </ShellSection>
  );
}

function WorkspaceLink({ entry, onClick }: { entry: WorkspaceEntry; onClick: () => void }) {
  const Icon = entry.icon;

  return (
    <button
      className={cn(
        "group flex min-h-28 w-full items-start gap-3 bg-card px-5 py-4 text-left transition-colors hover:bg-muted/60 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
      )}
      onClick={onClick}
      type="button"
    >
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-lg border bg-background text-muted-foreground transition-colors group-hover:text-foreground",
          entry.primary && "border-primary/20 bg-primary/10 text-primary",
        )}
      >
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-3 font-medium text-sm">
          {entry.title}
          <ArrowRight className="size-3.5 -translate-x-1 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
        </span>
        <span className="mt-1.5 block text-muted-foreground text-xs leading-5">{entry.description}</span>
      </span>
    </button>
  );
}

function OverviewSkeleton() {
  return (
    <>
      <Skeleton className="h-44 w-full rounded-xl" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {["requirements", "cases", "adoption", "automation"].map((item) => (
          <Card key={item} size="sm">
            <CardContent className="space-y-3 p-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-4 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(19rem,0.75fr)]">
        <Skeleton className="h-[26rem] w-full rounded-xl" />
        <Skeleton className="h-[26rem] w-full rounded-xl" />
      </div>
    </>
  );
}

function OverviewError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="border-destructive/30 bg-destructive/5" size="sm">
      <CardContent className="flex flex-col gap-3 p-4 text-destructive text-sm sm:flex-row sm:items-center sm:justify-between">
        <span className="flex items-center gap-2">
          <AlertTriangle className="size-4" />
          {message}
        </span>
        <Button onClick={onRetry} size="sm" variant="outline">
          重新加载
        </Button>
      </CardContent>
    </Card>
  );
}
