"use client";

import { useEffect, useState } from "react";

import { useParams } from "next/navigation";

import { FolderCog, ShieldCheck, SlidersHorizontal } from "lucide-react";

import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { moduleBreadcrumbs } from "@/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import { apiRequest, type ApiProject } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

export default function Page() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const [project, setProject] = useState<ApiProject | null>(null);
  const projectName = project?.name ?? "项目";

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    let ignore = false;

    async function loadProject() {
      try {
        const projects = await apiRequest<ApiProject[]>("/projects");
        const nextProject = projects.find((item) => item.id === projectId) ?? null;
        if (!ignore) {
          setProject(nextProject);
        }
      } catch {
        if (!ignore) {
          setProject(null);
        }
      }
    }

    void loadProject();

    return () => {
      ignore = true;
    };
  }, [projectId]);

  return (
    <PageShell
      breadcrumbs={moduleBreadcrumbs(
        "projects",
        { label: projectName, href: `/projects/${projectId}` },
        { label: "项目设置" },
      )}
      description="维护项目基础信息、成员权限、环境配置和测试资产策略。"
      primaryAction="保存设置"
      projectScope="project"
      activeTab="项目设置"
      tabs={[
        { label: "项目概览", href: `/projects/${projectId}` },
        { label: "项目设置", href: `/projects/${projectId}/settings` },
        "成员",
        "环境配置",
      ]}
      title="项目设置"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard helper="基础信息已维护" icon={FolderCog} label="项目资料" value="完整" />
        <MetricCard helper="管理员 3 人" icon={ShieldCheck} label="权限范围" value="已配置" />
        <MetricCard helper="测试 / 预发 / 生产" icon={SlidersHorizontal} label="环境配置" value="3" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ShellSection className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-medium text-sm">基础设置</h2>
              <p className="text-muted-foreground text-xs">项目名称、状态和说明。</p>
            </div>
          </div>
          <div className="grid gap-3 text-sm md:grid-cols-2">
            <p>项目名称：{project?.name ?? "-"}</p>
            <p>项目 ID：{projectId}</p>
            <p>项目状态：{project?.status === "archived" ? "归档" : "活跃"}</p>
            <p className="md:col-span-2">说明：{project?.description ?? "-"}</p>
          </div>
        </ShellSection>
        <ShellSection>
          <h2 className="mb-3 font-medium text-sm">项目操作</h2>
          <div className="flex flex-col gap-2">
            <Button variant="outline">配置成员权限</Button>
            <Button variant="outline">配置环境变量</Button>
            <Button variant="outline">归档项目</Button>
            <Button>保存设置</Button>
          </div>
        </ShellSection>
      </div>
    </PageShell>
  );
}
