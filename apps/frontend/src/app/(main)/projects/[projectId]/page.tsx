"use client";

import { useCallback, useEffect, useState } from "react";

import { useParams, useRouter } from "next/navigation";

import { ClipboardCheck, FileText, ListChecks, PlaySquare } from "lucide-react";
import { toast } from "sonner";

import { MetricCard, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import { useProjectContextStore } from "@/stores/project-context-store";

const PROJECT_LIST_CHANGED_EVENT = "ai-testing:project-list-changed";
const statusOptions = ["活跃", "归档"];
const statusToLabel = (status: ApiProject["status"]) => (status === "archived" ? "归档" : "活跃");
const labelToStatus = (label: string): ApiProject["status"] => (label === "归档" ? "archived" : "active");

export default function Page() {
  const router = useRouter();
  const hydrate = useProjectContextStore((state) => state.hydrate);
  const selectProject = useProjectContextStore((state) => state.selectProject);
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [projectName, setProjectName] = useState("项目");
  const [project, setProject] = useState<ApiProject | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({
    description: "",
    name: "",
    status: "活跃",
  });

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const loadProject = useCallback(async () => {
    try {
      const projects = await apiRequest<ApiProject[]>("/projects");
      const nextProject = projects.find((item) => item.id === projectId) ?? null;
      setProject(nextProject);
      setProjectName(nextProject?.name ?? "项目");
      if (nextProject) {
        setForm({
          description: nextProject.description,
          name: nextProject.name,
          status: statusToLabel(nextProject.status),
        });
      }
    } catch {
      setProject(null);
      setProjectName("项目");
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

  function openEditDialog() {
    if (project) {
      setForm({
        description: project.description,
        name: project.name,
        status: statusToLabel(project.status),
      });
    }
    setDialogOpen(true);
  }

  async function submitProject() {
    const name = form.name.trim();
    if (!name) {
      return;
    }

    try {
      await apiRequest<ApiProject>(`/projects/${projectId}`, {
        body: JSON.stringify({
          description: form.description.trim(),
          name,
          status: labelToStatus(form.status),
        }),
        method: "PATCH",
      });
      await loadProject();
      window.dispatchEvent(new Event(PROJECT_LIST_CHANGED_EVENT));
      toast.success("项目已保存");
      setDialogOpen(false);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "项目保存失败");
    }
  }

  return (
    <>
      <PageShell
        breadcrumbs={["项目工作区", "项目", projectName]}
        description=""
        onPrimaryAction={openEditDialog}
        primaryAction="编辑项目"
        projectScope="project"
        title={projectName}
      >
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard helper="真实接口接入后展示" icon={FileText} label="需求数" value="-" />
          <MetricCard helper="真实接口接入后展示" icon={ClipboardCheck} label="用例数" value="-" />
          <MetricCard helper="真实接口接入后展示" icon={PlaySquare} label="UI 自动化数量" value="-" />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <ShellSection className="lg:col-span-2">
            <h2 className="mb-3 font-medium text-sm">项目概览</h2>
            <div className="space-y-3 text-sm">
              <p>项目 ID：{projectId}</p>
              <p>项目描述：{project?.description ?? "-"}</p>
              <p>状态：{project?.status === "archived" ? "归档" : "活跃"}</p>
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
                <ListChecks className="size-4" />
                项目日志
              </Button>
              <Button onClick={() => goToModule("/test-cases")}>进入测试用例</Button>
            </div>
          </ShellSection>
        </div>
      </PageShell>
      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑项目</DialogTitle>
            <DialogDescription>修改项目名称、状态和描述信息。</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="project-name">项目名称</FieldLabel>
              <Input
                id="project-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="请输入项目名称"
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="project-status">项目状态</FieldLabel>
              <Select
                id="project-status"
                placeholder="选择项目状态"
                setValue={(value) => setForm((current) => ({ ...current, status: value }))}
                value={form.status}
              >
                {statusOptions.map((status) => (
                  <SelectOption key={status} value={status}>
                    {status}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="project-description">项目描述</FieldLabel>
              <Textarea
                id="project-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="请输入项目描述"
                value={form.description}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!form.name.trim()} onClick={submitProject} type="button">
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
