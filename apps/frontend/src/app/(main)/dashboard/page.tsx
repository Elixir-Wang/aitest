"use client";

import { useEffect, useMemo, useState } from "react";

import { AlertTriangle, ClipboardCheck, FolderKanban, Gauge, PlaySquare, type LucideIcon } from "lucide-react";

import { AssetTrendChart } from "@/app/(main)/dashboard/_components/asset-trend-chart";
import { MetricCard, PageShell } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiRequest, type ApiDashboardOverview } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

const metricIcons: Record<string, LucideIcon> = {
  项目数: FolderKanban,
  用例资产数: ClipboardCheck,
  测试用例采纳率: Gauge,
  自动化用例数量: PlaySquare,
};

export default function Page() {
  const { currentProjectId, hydrate, scope } = useProjectContextStore();
  const [overview, setOverview] = useState<ApiDashboardOverview | null>(null);
  const [trendDays, setTrendDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const projectId = scope === "project" && currentProjectId ? currentProjectId : "all";

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    let ignore = false;

    async function loadOverview() {
      setLoading(true);
      setError("");
      try {
        const result = await apiRequest<ApiDashboardOverview>(`/dashboard/overview?project_id=${projectId}&days=${trendDays}`);
        if (!ignore) {
          setOverview(result);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "控制台数据加载失败");
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    void loadOverview();

    return () => {
      ignore = true;
    };
  }, [projectId, trendDays]);

  const projectLabel = useMemo(() => {
    if (!overview || overview.scope === "all") {
      return "当前项目权限范围";
    }
    return overview.project_name ?? "当前项目";
  }, [overview]);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("dashboard")}
      description="跨项目查看测试资产规模、采纳情况和自动化建设进度。"
      projectScope="all"
      title="控制台"
    >
      {error ? <DashboardError message={error} /> : null}
      {loading ? <DashboardSkeleton /> : null}
      {!loading && overview ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {overview.metrics.map((metric) => (
              <MetricCard
                helper={metric.helper}
                icon={metricIcons[metric.label] ?? ClipboardCheck}
                key={metric.label}
                label={metric.label}
                value={metric.value}
              />
            ))}
          </div>
          <AssetTrendChart data={overview.trend} days={trendDays} onDaysChange={setTrendDays} projectLabel={projectLabel} />
        </>
      ) : null}
    </PageShell>
  );
}

function DashboardSkeleton() {
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {["projects", "cases", "adoption", "automation"].map((item) => (
          <Card key={item} size="sm">
            <CardContent className="space-y-3 p-4">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-4 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Skeleton className="h-96 w-full rounded-lg" />
    </>
  );
}

function DashboardError({ message }: { message: string }) {
  return (
    <Card className="border-destructive/30 bg-destructive/5" size="sm">
      <CardContent className="flex items-center justify-between gap-3 p-4 text-destructive text-sm">
        <span className="flex items-center gap-2">
          <AlertTriangle className="size-4" />
          {message}
        </span>
        <Button size="sm" variant="outline" onClick={() => window.location.reload()}>
          重新加载
        </Button>
      </CardContent>
    </Card>
  );
}
