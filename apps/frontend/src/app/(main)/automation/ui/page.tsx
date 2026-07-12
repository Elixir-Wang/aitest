"use client";

import { useCallback, useEffect, useState } from "react";

import { Loader2, Play, RotateCcw, Square } from "lucide-react";
import { toast } from "sonner";

import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { chineseCompletionTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";

type Operation = {
  key: string;
  version: number;
  status: string;
  page_path: string;
  parameters: Record<string, { type: string; required: boolean; default: unknown }>;
  steps: Array<{ action: string; element_key: string }>;
};

type OperationsArtifact = { operations: Operation[] };
type ReplayRun = {
  id: string;
  project_id: string;
  environment_id: string;
  operation_key: string;
  status: string;
  steps: Array<{ index: number; action: string; element_key: string; success: boolean }>;
  error: string;
};

export default function Page() {
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [projectId, setProjectId] = useState("");
  const [environments, setEnvironments] = useState<ExplorationEnvironment[]>([]);
  const [environmentId, setEnvironmentId] = useState("");
  const [operations, setOperations] = useState<Operation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOperation, setSelectedOperation] = useState<Operation | null>(null);
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [run, setRun] = useState<ReplayRun | null>(null);

  useEffect(() => {
    apiRequest<ApiProject[]>("/projects")
      .then((items) => {
        const active = items.filter((item) => item.status === "active");
        setProjects(active);
        setProjectId(active[0]?.id || "");
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "项目加载失败"));
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    Promise.all([
      apiRequest<ExplorationEnvironment[]>(`/environments?project_id=${projectId}`),
      apiRequest<OperationsArtifact>(`/page-exploration/projects/${projectId}/operations`),
    ])
      .then(([environmentItems, artifact]) => {
        setEnvironments(environmentItems);
        setEnvironmentId(environmentItems[0]?.id || "");
        setOperations(artifact.operations || []);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "自动化产物加载失败"))
      .finally(() => setLoading(false));
  }, [projectId]);

  const pollRun = useCallback(async (project: string, runId: string) => {
    const next = await apiRequest<ReplayRun>(`/page-exploration/projects/${project}/replay-runs/${runId}`);
    setRun(next);
    if (["pending", "running", "stopping"].includes(next.status)) {
      window.setTimeout(() => void pollRun(project, runId), 1000);
    }
  }, []);

  async function startRun() {
    if (!selectedOperation || !environmentId) return;
    try {
      const created = await apiRequest<ReplayRun>(`/page-exploration/projects/${projectId}/replay`, {
        method: "POST",
        body: JSON.stringify({
          environment_id: environmentId,
          operation_key: selectedOperation.key,
          parameters,
        }),
      });
      setSelectedOperation(null);
      setRun(created);
      void pollRun(projectId, created.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "执行启动失败");
    }
  }

  async function runAction(action: "stop" | "retry") {
    if (!run) return;
    const next = await apiRequest<ReplayRun>(
      `/page-exploration/projects/${run.project_id}/replay-runs/${run.id}/${action}`,
      { method: "POST" },
    );
    setRun(next);
    if (action === "retry") void pollRun(next.project_id, next.id);
  }

  return (
    <PageShell
      breadcrumbs={[{ label: "测试资产" }, { label: "UI 自动化" }]}
      description="使用项目级探索产物，在当前项目任意环境中执行 Chrome 自动化。"
      projectScope="all"
      title="UI 自动化"
    >
      <ShellSection>
        <div className="flex flex-wrap items-end gap-4 border-b p-4">
          <Field className="w-64">
            <FieldLabel>项目</FieldLabel>
            <Select placeholder="选择项目" setValue={setProjectId} value={projectId}>
              {projects.map((project) => (
                <SelectOption key={project.id} value={project.id}>
                  {project.name}
                </SelectOption>
              ))}
            </Select>
          </Field>
          <Field className="w-64">
            <FieldLabel>运行环境</FieldLabel>
            <Select placeholder="选择项目环境" setValue={setEnvironmentId} value={environmentId}>
              {environments.map((environment) => (
                <SelectOption key={environment.id} value={environment.id}>
                  {environment.name}
                </SelectOption>
              ))}
            </Select>
          </Field>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>操作</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>入口路径</TableHead>
              <TableHead>步骤</TableHead>
              <TableHead className="w-20">执行</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell className="h-24 text-center" colSpan={5}>
                  <Loader2 className="mx-auto size-5 animate-spin" />
                </TableCell>
              </TableRow>
            ) : null}
            {!loading &&
              operations.map((operation) => (
                <TableRow key={operation.key}>
                  <TableCell className="font-medium">{operation.key}</TableCell>
                  <TableCell>
                    <StatusBadge tone={chineseCompletionTone(operation.status)}>{operation.status}</StatusBadge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{operation.page_path}</TableCell>
                  <TableCell>{operation.steps.length}</TableCell>
                  <TableCell>
                    <Button
                      aria-label={`执行 ${operation.key}`}
                      disabled={!environmentId || ["degraded", "deprecated"].includes(operation.status)}
                      onClick={() => {
                        setSelectedOperation(operation);
                        setParameters({});
                      }}
                      size="icon-sm"
                    >
                      <Play className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            {!loading && operations.length === 0 ? (
              <TableRow>
                <TableCell className="h-24 text-center text-muted-foreground" colSpan={5}>
                  当前项目暂无可执行操作。
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </ShellSection>
      {run ? (
        <ShellSection>
          <div className="flex items-center justify-between border-b p-4">
            <div>
              <div className="font-medium">{run.operation_key}</div>
              <div className="text-muted-foreground text-sm">{run.id}</div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge tone={chineseCompletionTone(run.status)}>{run.status}</StatusBadge>
              {["pending", "running"].includes(run.status) ? (
                <Button onClick={() => void runAction("stop")} size="icon-sm" variant="outline">
                  <Square className="size-4" />
                </Button>
              ) : (
                <Button onClick={() => void runAction("retry")} size="icon-sm" variant="outline">
                  <RotateCcw className="size-4" />
                </Button>
              )}
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>动作</TableHead>
                <TableHead>元素</TableHead>
                <TableHead>结果</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.steps.map((step) => (
                <TableRow key={step.index}>
                  <TableCell>{step.index}</TableCell>
                  <TableCell>{step.action}</TableCell>
                  <TableCell className="font-mono text-xs">{step.element_key || "-"}</TableCell>
                  <TableCell>{step.success ? "通过" : "失败"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ShellSection>
      ) : null}
      <Dialog
        open={Boolean(selectedOperation)}
        onOpenChange={(open) => {
          if (!open) setSelectedOperation(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>执行 {selectedOperation?.key}</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            {Object.entries(selectedOperation?.parameters || {}).map(([name, spec]) => (
              <Field key={name}>
                <FieldLabel htmlFor={`replay-${name}`}>
                  {name}
                  {spec.required ? " *" : ""}
                </FieldLabel>
                <Input
                  id={`replay-${name}`}
                  onChange={(event) => setParameters((current) => ({ ...current, [name]: event.target.value }))}
                  value={parameters[name] || String(spec.default ?? "")}
                />
              </Field>
            ))}
          </FieldGroup>
          <DialogFooter>
            <Button onClick={() => setSelectedOperation(null)} variant="outline">
              取消
            </Button>
            <Button disabled={!environmentId} onClick={() => void startRun()}>
              <Play className="size-4" />
              开始执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
