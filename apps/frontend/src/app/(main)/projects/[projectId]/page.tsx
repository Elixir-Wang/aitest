"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ClipboardCheck, FileText, Gauge } from "lucide-react";

import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import {
  type ApiDashboardOverview,
  type ApiProject,
  type ApiRequirementDocument,
  apiRequest,
  formatDateTime,
} from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

const statusToLabel = (status: ApiProject["status"]) => (status === "archived" ? "归档" : "活跃");

export default function Page() {
  const router = useRouter();
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const selectProject = useProjectContextStore((state) => state.selectProject);
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [projectName, setProjectName] = useState("项目");
  const [project, setProject] = useState<ApiProject | null>(null);
  const [overview, setOverview] = useState<ApiDashboardOverview | null>(null);
  const [requirementCount, setRequirementCount] = useState<number | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const loadProject = useCallback(async () => {
    try {
      const [projects, projectOverview, requirements] = await Promise.all([
        apiRequest<ApiProject[]>("/projects"),
        apiRequest<ApiDashboardOverview>(`/dashboard/overview?project_id=${projectId}&days=30`),
        apiRequest<ApiRequirementDocument[]>(`/projects/${projectId}/requirements`),
      ]);
      const nextProject = projects.find((item) => item.id === projectId) ?? null;
      setProject(nextProject);
      setProjectName(nextProject?.name ?? "项目");
      setOverview(projectOverview);
      setRequirementCount(requirements.length);
    } catch {
      setProject(null);
      setProjectName("项目");
      setOverview(null);
      setRequirementCount(null);
    }
  }, [projectId]);

  useEffect(() => {
    let ignore = false;

    async function load() {
      if (!ignore) {
        await loadProject();
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [loadProject]);

  function goToModule(path: string) {
    selectProject(projectId);
    router.push(path);
  }

  const metricByLabel = useMemo(
    () => new Map((overview?.metrics ?? []).map((metric) => [metric.label, metric])),
    [overview],
  );
  const caseAssetMetric = metricByLabel.get("用例资产数");
  const adoptionMetric = metricByLabel.get("测试用例采纳率");
  const requirementCountValue = requirementCount === null ? "-" : String(requirementCount);
  const caseAssetValue = caseAssetMetric?.value ?? "-";
  const adoptionRateValue = adoptionMetric?.value ?? "-";

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs("projects", { label: projectName })}
      description=""
      projectScope="project"
      title={projectName}
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          helper={requirementCount === null ? "需求文档加载中" : `需求文档 ${requirementCount} 份`}
          icon={FileText}
          label="需求数"
          value={requirementCountValue}
        />
        <MetricCard
          helper={caseAssetMetric?.helper ?? "已采纳 - 条"}
          icon={ClipboardCheck}
          label="用例数"
          value={caseAssetValue}
        />
        <MetricCard
          helper={adoptionMetric?.helper ?? "较上周 -"}
          icon={Gauge}
          label="用例采纳率"
          value={adoptionRateValue}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ShellSection className="lg:col-span-2">
          <h2 className="mb-3 font-medium text-sm">项目概览</h2>
          <div className="space-y-3 text-sm">
            <p>项目名称：{project?.name ?? "-"}</p>
            <p>项目描述：{project?.description || "-"}</p>
            <p>状态：{project ? statusToLabel(project.status) : "-"}</p>
            <p>创建时间：{formatDateTime(project?.created_at ?? null)}</p>
            <p>最近更新：{formatDateTime(project?.updated_at ?? null)}</p>
          </div>
        </ShellSection>
        <ShellSection>
          <h2 className="mb-3 font-medium text-sm">可用操作</h2>
          <div className="flex flex-col gap-2">
            <Button variant="outline" onClick={() => goToModule("/requirements")}>
              进入需求
            </Button>
            <Button variant="outline" onClick={() => goToModule("/exploration")}>
              进入探索
            </Button>
            <Button variant="outline" onClick={() => goToModule(`/projects/${projectId}/logs`)}>
              项目日志
            </Button>
            <Button onClick={() => goToModule("/test-cases")}>进入测试用例</Button>
          </div>
        </ShellSection>
      </div>
    </PageShell>
  );
}
