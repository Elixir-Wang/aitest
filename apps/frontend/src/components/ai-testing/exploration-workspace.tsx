"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSearchParams } from "next/navigation";

import { Eye, EyeOff, Pencil, Play, Plus, Square, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
import { Select, SelectOption } from "@/components/ui/animated-select-1";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { type ApiProject, apiRequest, formatDateTime } from "@/lib/api-client";
import { createRunningTaskId, useRunningTaskStore } from "@/stores/running-task-store";

type ProjectScope = "all" | "project";

type ProjectEnvironment = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  site_url: string;
  username: string;
  password_mask: string;
  login_strategy: string;
  description: string;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

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
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

type ExplorationWorkspaceProps = {
  breadcrumbs: string[];
  description: string;
  projectId?: string;
  projectName?: string;
  projectScope: ProjectScope;
  title: string;
};

type EnvironmentForm = {
  name: string;
  projectId: string;
  siteUrl: string;
  username: string;
  password: string;
  loginStrategy: string;
  description: string;
};

type ExplorationForm = {
  title: string;
  projectId: string;
  environmentId: string;
  scope: string;
  forbiddenPaths: string;
  description: string;
};

const emptyForm: EnvironmentForm = {
  name: "",
  projectId: "",
  siteUrl: "",
  username: "",
  password: "",
  loginStrategy: "reuse_state",
  description: "",
};

const emptyExplorationForm: ExplorationForm = {
  title: "",
  projectId: "",
  environmentId: "",
  scope: "",
  forbiddenPaths: "",
  description: "",
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

const loginStrategyLabels: Record<string, string> = {
  reuse_state: "复用登录态",
  manual: "手动登录保存状态",
  account_password: "账号密码",
  skip_login: "跳过登录",
};

const explorationTabs = ["探索列表", "探索环境"];
const RUNNING_EXPLORATION_STATUSES = new Set(["queued", "running", "waiting_human", "stopping"]);
const STOPPABLE_EXPLORATION_STATUSES = new Set(["queued", "running", "waiting_human"]);
const EXPLORATION_TASK_SOURCE = "exploration-page";

export function ExplorationWorkspace({
  breadcrumbs,
  description,
  projectId,
  projectName = "",
  projectScope,
  title,
}: ExplorationWorkspaceProps) {
  const searchParams = useSearchParams();
  const createParamHandledRef = useRef(false);
  const [activeTab, setActiveTab] = useState("探索列表");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [explorationDialogOpen, setExplorationDialogOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<ProjectEnvironment | null>(null);
  const [editingExploration, setEditingExploration] = useState<ExplorationRun | null>(null);
  const [stoppingExploration, setStoppingExploration] = useState<ExplorationRun | null>(null);
  const [stoppingExplorationId, setStoppingExplorationId] = useState("");
  const [explorationLoading, setExplorationLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(true);
  const [projectLoading, setProjectLoading] = useState(projectScope === "all");
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const replaceRunningTasksBySource = useRunningTaskStore((state) => state.replaceTasksBySource);
  const [form, setForm] = useState<EnvironmentForm>({ ...emptyForm, projectId: projectId ?? "" });
  const [explorationForm, setExplorationForm] = useState<ExplorationForm>({
    ...emptyExplorationForm,
    projectId: projectId ?? "",
  });
  const explorationSelection = useLocalTableSelection<ExplorationRun>([]);
  const {
    allSelected,
    clearSelection,
    partiallySelected,
    rows,
    selectedCount,
    selectedIds,
    setRows,
    toggleAll,
    toggleOne,
  } = useLocalTableSelection<ProjectEnvironment>([]);

  useEffect(() => {
    setForm((current) => ({ ...current, projectId: projectId ?? current.projectId }));
    setExplorationForm((current) => ({ ...current, projectId: projectId ?? current.projectId }));
  }, [projectId]);

  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      setProjectLoading(true);
      try {
        const data = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(data);
          if (projectScope === "all") {
            setForm((current) => ({ ...current, projectId: current.projectId || data[0]?.id || "" }));
          }
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "项目列表加载失败");
        }
      } finally {
        if (!ignore) {
          setProjectLoading(false);
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, [projectScope]);

  useEffect(() => {
    let ignore = false;

    async function loadEnvironments() {
      setEnvironmentLoading(true);
      setError("");
      try {
        const path = projectScope === "project" && projectId ? `/projects/${projectId}/environments` : "/environments";
        const data = await apiRequest<ProjectEnvironment[]>(path);
        if (!ignore) {
          setRows(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "环境列表加载失败");
        }
      } finally {
        if (!ignore) {
          setEnvironmentLoading(false);
        }
      }
    }

    void loadEnvironments();

    return () => {
      ignore = true;
    };
  }, [projectId, projectScope, setRows]);

  useEffect(() => {
    let ignore = false;

    async function loadExplorationRuns() {
      setExplorationLoading(true);
      setError("");
      try {
        const path =
          projectScope === "project" && projectId ? `/projects/${projectId}/exploration-runs` : "/exploration-runs";
        const data = await apiRequest<ExplorationRun[]>(path);
        if (!ignore) {
          explorationSelection.setRows(data);
          replaceRunningTasksBySource(
            EXPLORATION_TASK_SOURCE,
            data
              .filter((item) => RUNNING_EXPLORATION_STATUSES.has(item.status))
              .map((item) => ({
                id: createRunningTaskId(EXPLORATION_TASK_SOURCE, item.id),
                projectId: item.project_id,
                projectName: item.project_name,
                title: item.title,
                moduleLabel: "站点探索",
                status: item.status,
                statusLabel: statusLabels[item.status] ?? item.status,
                updatedAt: item.updated_at,
              })),
          );
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "探索任务加载失败");
        }
      } finally {
        if (!ignore) {
          setExplorationLoading(false);
        }
      }
    }

    void loadExplorationRuns();

    return () => {
      ignore = true;
    };
  }, [projectId, projectScope, explorationSelection.setRows, replaceRunningTasksBySource]);

  const filteredRows = useMemo(
    () =>
      rows.filter((item) =>
        [item.name, item.project_name, item.site_url, item.username, item.description, item.updated_at].some((value) =>
          value.toLowerCase().includes(searchText.trim().toLowerCase()),
        ),
      ),
    [rows, searchText],
  );

  const filteredExplorationRows = useMemo(
    () =>
      explorationSelection.rows.filter((item) =>
        [
          item.title,
          item.project_name,
          item.environment_name,
          statusLabels[item.status] ?? item.status,
          item.scope,
          item.description,
          item.updated_at,
        ].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase())),
      ),
    [explorationSelection.rows, searchText],
  );

  const scopedProjectName =
    (projectName.trim() ? projectName : undefined) ??
    projects.find((project) => project.id === projectId)?.name ??
    rows.find((environment) => environment.project_id === projectId)?.project_name ??
    explorationSelection.rows.find((run) => run.project_id === projectId)?.project_name ??
    projectId ??
    "";
  const environmentProjectValue = projectScope === "project" ? (projectId ?? "") : form.projectId;
  const explorationProjectValue = projectScope === "project" ? (projectId ?? "") : explorationForm.projectId;
  const canCreateEnvironment = projectScope === "project" || form.projectId.length > 0;
  const selectedProjectId = projectScope === "project" ? (projectId ?? "") : explorationForm.projectId;
  const availableEnvironments = rows.filter((environment) => environment.project_id === selectedProjectId);
  const canCreateExploration = selectedProjectId.length > 0 && explorationForm.environmentId.length > 0;
  const explorationProjectSelectDisabled = [
    projectScope === "project",
    projectLoading,
    editingExploration !== null,
  ].some(Boolean);
  const environmentProjectSelectDisabled = [
    projectScope === "project",
    projectLoading,
    editingEnvironment !== null,
  ].some(Boolean);

  function openCreateDialog() {
    setEditingEnvironment(null);
    setForm({ ...emptyForm, projectId: projectId ?? projects[0]?.id ?? "" });
    setShowPassword(false);
    setDialogOpen(true);
  }

  const openCreateExplorationDialog = useCallback(() => {
    const targetProjectId = projectId ?? projects[0]?.id ?? "";
    const firstEnvironment = rows.find((environment) => environment.project_id === targetProjectId);
    setEditingExploration(null);
    setExplorationForm({
      ...emptyExplorationForm,
      projectId: targetProjectId,
      environmentId: firstEnvironment?.id ?? "",
    });
    setExplorationDialogOpen(true);
  }, [projectId, projects, rows]);

  useEffect(() => {
    if (searchParams.get("create") !== "exploration" || createParamHandledRef.current) {
      return;
    }

    createParamHandledRef.current = true;
    setActiveTab("探索列表");
    openCreateExplorationDialog();
  }, [openCreateExplorationDialog, searchParams]);

  function openEditDialog(environment: ProjectEnvironment) {
    setEditingEnvironment(environment);
    setForm({
      name: environment.name,
      projectId: environment.project_id,
      siteUrl: environment.site_url,
      username: environment.username,
      password: "",
      loginStrategy: environment.login_strategy,
      description: environment.description,
    });
    setShowPassword(false);
    setDialogOpen(true);
  }

  function openEditExplorationDialog(run: ExplorationRun) {
    setEditingExploration(run);
    setExplorationForm({
      title: run.title,
      projectId: run.project_id,
      environmentId: run.environment_id,
      scope: run.scope,
      forbiddenPaths: run.forbidden_paths,
      description: run.description,
    });
    setExplorationDialogOpen(true);
  }

  async function saveEnvironment() {
    const targetProjectId = projectScope === "project" ? projectId : form.projectId;
    if (!targetProjectId) {
      toast.error("请选择项目");
      return;
    }
    if (!form.name.trim() || !form.siteUrl.trim()) {
      toast.error("请填写环境名称和站点地址");
      return;
    }

    try {
      if (editingEnvironment) {
        // 更新环境
        const payload: Record<string, string> = {
          name: form.name,
          site_url: form.siteUrl,
          username: form.username,
          login_strategy: form.loginStrategy,
          description: form.description,
        };
        // 只有填写了密码才更新密码
        if (form.password) {
          payload.password = form.password;
        }

        const updated = await apiRequest<ProjectEnvironment>(
          `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}`,
          {
            method: "PATCH",
            body: JSON.stringify(payload),
          },
        );
        setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        toast.success("环境已更新");
      } else {
        // 创建环境
        const created = await apiRequest<ProjectEnvironment>(`/projects/${targetProjectId}/environments`, {
          method: "POST",
          body: JSON.stringify({
            project_id: targetProjectId,
            name: form.name,
            site_url: form.siteUrl,
            username: form.username,
            password: form.password,
            login_strategy: form.loginStrategy,
            description: form.description,
          }),
        });
        setRows((current) => [created, ...current]);
        toast.success("环境已创建");
      }
      setForm({ ...emptyForm, projectId: projectId ?? form.projectId });
      setDialogOpen(false);
    } catch (requestError) {
      toast.error(
        requestError instanceof Error ? requestError.message : editingEnvironment ? "环境更新失败" : "环境创建失败",
      );
    }
  }

  async function saveExplorationRun() {
    const targetProjectId = projectScope === "project" ? projectId : explorationForm.projectId;
    if (!targetProjectId) {
      toast.error("请选择项目");
      return;
    }
    if (!explorationForm.title.trim() || !explorationForm.environmentId) {
      toast.error("请填写任务名称并选择环境");
      return;
    }

    try {
      const payload = {
        environment_id: explorationForm.environmentId,
        title: explorationForm.title,
        scope: explorationForm.scope,
        forbidden_paths: explorationForm.forbiddenPaths,
        description: explorationForm.description,
      };
      if (editingExploration) {
        const updated = await apiRequest<ExplorationRun>(
          `/projects/${editingExploration.project_id}/exploration-runs/${editingExploration.id}`,
          {
            method: "PATCH",
            body: JSON.stringify(payload),
          },
        );
        explorationSelection.setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        toast.success("探索任务已更新");
      } else {
        const created = await apiRequest<ExplorationRun>(`/projects/${targetProjectId}/exploration-runs`, {
          method: "POST",
          body: JSON.stringify({
            project_id: targetProjectId,
            ...payload,
          }),
        });
        explorationSelection.setRows((current) => [created, ...current]);
        toast.success("探索任务已创建");
      }
      setExplorationDialogOpen(false);
      setEditingExploration(null);
    } catch (requestError) {
      toast.error(
        requestError instanceof Error
          ? requestError.message
          : editingExploration
            ? "探索任务更新失败"
            : "探索任务创建失败",
      );
    }
  }

  async function deleteExplorationRuns(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    try {
      await Promise.all(
        ids.map((id) => {
          const run = explorationSelection.rows.find((item) => item.id === id);
          if (!run) {
            return Promise.resolve();
          }
          return apiRequest(`/projects/${run.project_id}/exploration-runs/${id}`, { method: "DELETE" });
        }),
      );
      explorationSelection.setRows((current) => current.filter((row) => !ids.includes(row.id)));
      explorationSelection.clearSelection();
      toast.success(`已删除 ${ids.length} 个探索任务`);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务删除失败");
    }
  }

  async function stopExplorationRun(run: ExplorationRun) {
    setStoppingExplorationId(run.id);
    try {
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/stop`, {
        method: "POST",
      });
      explorationSelection.setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      toast.success("探索任务已停止");
      setStoppingExploration(null);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务停止失败");
    } finally {
      setStoppingExplorationId("");
    }
  }

  function openExplorationRun(run: ExplorationRun) {
    window.location.href = `/projects/${run.project_id}/exploration/${run.id}`;
  }

  async function deleteEnvironments(ids: string[]) {
    if (ids.length === 0) {
      return;
    }
    try {
      await Promise.all(
        ids.map((id) => {
          const environment = rows.find((item) => item.id === id);
          if (!environment) {
            return Promise.resolve();
          }
          return apiRequest(`/projects/${environment.project_id}/environments/${id}`, { method: "DELETE" });
        }),
      );
      setRows((current) => current.filter((row) => !ids.includes(row.id)));
      clearSelection();
      toast.success(`已删除 ${ids.length} 个环境`);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "环境删除失败");
    }
  }

  return (
    <PageShell
      activeTab={activeTab}
      breadcrumbs={breadcrumbs}
      description={description}
      projectScope={projectScope}
      tabs={explorationTabs}
      title={title}
      onTabChange={setActiveTab}
    >
      {activeTab === "探索列表" ? (
        <ShellSection>
          {error ? (
            <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
              {error}
            </div>
          ) : null}
          <ListToolbar
            createLabel="新建探索任务"
            onBatchDelete={() => deleteExplorationRuns(explorationSelection.selectedIds)}
            onCreate={openCreateExplorationDialog}
            onSearch={setSearchText}
            placeholder="搜索探索任务"
            selectedCount={explorationSelection.selectedCount}
            title="探索任务列表"
          />
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label="选择全部探索任务"
                      checked={
                        explorationSelection.allSelected ||
                        (explorationSelection.partiallySelected ? "indeterminate" : false)
                      }
                      disabled={explorationLoading}
                      onCheckedChange={(checked) => explorationSelection.toggleAll(Boolean(checked))}
                    />
                  </TableHead>
                  <TableHead>任务名称</TableHead>
                  <TableHead>项目</TableHead>
                  <TableHead>关联环境</TableHead>
                  <TableHead>任务状态</TableHead>
                  <TableHead>登录策略</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="w-16">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredExplorationRows.map((item) => (
                  <TableRow
                    data-state={explorationSelection.selectedIds.includes(item.id) ? "selected" : undefined}
                    key={item.id}
                  >
                    <TableCell>
                      <Checkbox
                        aria-label={`选择 ${item.title}`}
                        checked={explorationSelection.selectedIds.includes(item.id)}
                        onCheckedChange={(checked) => explorationSelection.toggleOne(item.id, Boolean(checked))}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <button className="hover:underline" onClick={() => openExplorationRun(item)} type="button">
                        {item.title}
                      </button>
                    </TableCell>
                    <TableCell>{item.project_name}</TableCell>
                    <TableCell>{item.environment_name}</TableCell>
                    <TableCell>
                      <div className="flex min-w-36 items-center gap-2">
                        <span>{statusLabels[item.status] ?? item.status}</span>
                        {STOPPABLE_EXPLORATION_STATUSES.has(item.status) ? (
                          <Button
                            className="h-7 px-2 text-xs"
                            disabled={stoppingExplorationId === item.id}
                            onClick={() => setStoppingExploration(item)}
                            size="sm"
                            type="button"
                            variant="destructive"
                          >
                            <Square className="size-3.5" />
                            停止
                          </Button>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>{loginStrategyLabels[item.login_strategy] ?? item.login_strategy}</TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          {
                            label: "概览",
                            icon: Eye,
                            onSelect: () => openExplorationRun(item),
                          },
                          {
                            label: "编辑",
                            icon: Pencil,
                            onSelect: () => openEditExplorationDialog(item),
                          },
                          ...(STOPPABLE_EXPLORATION_STATUSES.has(item.status)
                            ? [
                                {
                                  label: "停止探索",
                                  icon: Square,
                                  destructive: true,
                                  onSelect: () => setStoppingExploration(item),
                                },
                              ]
                            : []),
                          {
                            label: "删除",
                            icon: Trash2,
                            destructive: true,
                            onSelect: () => deleteExplorationRuns([item.id]),
                          },
                        ]}
                        label={`打开 ${item.title} 操作菜单`}
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {explorationLoading && filteredExplorationRows.length === 0 ? (
                  <TableLoadingRow colSpan={8} label="探索任务加载中" />
                ) : null}
                {!explorationLoading && filteredExplorationRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={8}>
                      暂无探索任务。选择环境并创建探索任务后，系统会生成页面结构与探索报告。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      ) : null}

      {activeTab === "探索环境" ? (
        <ShellSection>
          {error ? (
            <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive text-sm">
              {error}
            </div>
          ) : null}
          <ListToolbar
            createLabel="新建环境"
            onBatchDelete={() => deleteEnvironments(selectedIds)}
            onCreate={openCreateDialog}
            onSearch={setSearchText}
            placeholder="搜索环境名称、项目、站点、用户名或描述"
            selectedCount={selectedCount}
            title="环境列表"
          />
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <Checkbox
                      aria-label="选择全部环境"
                      checked={allSelected || (partiallySelected ? "indeterminate" : false)}
                      disabled={environmentLoading}
                      onCheckedChange={(checked) => toggleAll(Boolean(checked))}
                    />
                  </TableHead>
                  <TableHead>环境名称</TableHead>
                  <TableHead>项目</TableHead>
                  <TableHead>站点地址</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead className="w-16">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredRows.map((item) => (
                  <TableRow data-state={selectedIds.includes(item.id) ? "selected" : undefined} key={item.id}>
                    <TableCell>
                      <Checkbox
                        aria-label={`选择 ${item.name}`}
                        checked={selectedIds.includes(item.id)}
                        onCheckedChange={(checked) => toggleOne(item.id, Boolean(checked))}
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <button className="hover:underline" onClick={() => openEditDialog(item)} type="button">
                        {item.name}
                      </button>
                    </TableCell>
                    <TableCell>{item.project_name}</TableCell>
                    <TableCell>
                      <span className="block max-w-72 truncate" title={item.site_url}>
                        {item.site_url}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="block max-w-64 truncate" title={item.description}>
                        {item.description || "-"}
                      </span>
                    </TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          {
                            label: "删除",
                            icon: Trash2,
                            destructive: true,
                            onSelect: () => deleteEnvironments([item.id]),
                          },
                        ]}
                        label={`打开 ${item.name} 操作菜单`}
                      />
                    </TableCell>
                  </TableRow>
                ))}
                {environmentLoading && filteredRows.length === 0 ? (
                  <TableLoadingRow colSpan={7} label="环境列表加载中" />
                ) : null}
                {!environmentLoading && filteredRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={7}>
                      暂无环境。新增站点环境后，可用于后续页面探索任务。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      ) : null}

      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="gap-6 p-6 sm:max-w-3xl">
          <DialogHeader className="gap-3">
            <DialogTitle>{editingEnvironment ? "编辑环境" : "新建环境"}</DialogTitle>
            <DialogDescription>
              填写环境名称、所属项目、站点地址、登录信息和登录策略，用于后续探索任务。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="environment-name">环境名称</FieldLabel>
              <Input
                id="environment-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="测试环境"
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-project">项目</FieldLabel>
              <Select
                disabled={environmentProjectSelectDisabled}
                id="environment-project"
                placeholder={projectScope === "project" ? scopedProjectName : "选择项目"}
                setValue={(value) => setForm((current) => ({ ...current, projectId: value }))}
                value={environmentProjectValue}
              >
                {projectScope === "project" && projectId ? (
                  <SelectOption value={projectId}>{scopedProjectName}</SelectOption>
                ) : (
                  projects.map((project) => (
                    <SelectOption key={project.id} value={project.id}>
                      {project.name}
                    </SelectOption>
                  ))
                )}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-site-url">站点地址</FieldLabel>
              <Input
                id="environment-site-url"
                onChange={(event) => setForm((current) => ({ ...current, siteUrl: event.target.value }))}
                placeholder="https://test.example.com"
                value={form.siteUrl}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-username">用户名</FieldLabel>
              <Input
                id="environment-username"
                onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="tester"
                value={form.username}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-login-strategy">登录策略</FieldLabel>
              <Select
                id="environment-login-strategy"
                placeholder="选择登录策略"
                setValue={(value) => setForm((current) => ({ ...current, loginStrategy: value }))}
                value={form.loginStrategy}
              >
                {Object.entries(loginStrategyLabels).map(([value, label]) => (
                  <SelectOption key={value} value={value}>
                    {label}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-password">
                {editingEnvironment ? "密码（留空表示不修改）" : "密码"}
              </FieldLabel>
              <div className="relative">
                <Input
                  className="pr-10"
                  id="environment-password"
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder={editingEnvironment ? "留空表示不修改密码" : "请输入密码"}
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                />
                <Button
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                  className="absolute top-1/2 right-1.5 size-7 -translate-y-1/2"
                  onClick={() => setShowPassword((current) => !current)}
                  size="icon"
                  type="button"
                  variant="ghost"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </div>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="environment-description">描述</FieldLabel>
              <Textarea
                className="min-h-20"
                id="environment-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="账号权限、验证码处理方式、探索范围或注意事项"
                value={form.description}
              />
            </Field>
          </FieldGroup>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!canCreateEnvironment} onClick={saveEnvironment} type="button">
              {editingEnvironment ? (
                "保存"
              ) : (
                <>
                  <Plus className="size-4" />
                  创建环境
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={(open) => !open && setStoppingExploration(null)} open={Boolean(stoppingExploration)}>
        <DialogContent className="gap-5 p-6 sm:max-w-md">
          <DialogHeader className="gap-3">
            <DialogTitle>停止探索任务</DialogTitle>
            <DialogDescription>停止后将终止当前浏览器探索进程，已生成的截图、日志和页面事实会保留。</DialogDescription>
          </DialogHeader>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setStoppingExploration(null)} type="button" variant="outline">
              继续探索
            </Button>
            <Button
              disabled={!stoppingExploration || stoppingExplorationId === stoppingExploration.id}
              onClick={() => stoppingExploration && stopExplorationRun(stoppingExploration)}
              type="button"
              variant="destructive"
            >
              <Square className="size-4" />
              停止探索
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        onOpenChange={(open) => {
          setExplorationDialogOpen(open);
          if (!open) {
            setEditingExploration(null);
          }
        }}
        open={explorationDialogOpen}
      >
        <DialogContent className="gap-6 p-6 sm:max-w-3xl">
          <DialogHeader className="gap-3">
            <DialogTitle>{editingExploration ? "编辑探索任务" : "新建探索任务"}</DialogTitle>
            <DialogDescription>选择环境并配置探索范围、禁止路径和任务说明。</DialogDescription>
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
              <FieldLabel htmlFor="exploration-project">项目</FieldLabel>
              <Select
                disabled={explorationProjectSelectDisabled}
                id="exploration-project"
                placeholder={projectScope === "project" ? scopedProjectName : "选择项目"}
                setValue={(value) => {
                  const firstEnvironment = rows.find((environment) => environment.project_id === value);
                  setExplorationForm((current) => ({
                    ...current,
                    projectId: value,
                    environmentId: firstEnvironment?.id ?? "",
                  }));
                }}
                value={explorationProjectValue}
              >
                {projectScope === "project" && projectId ? (
                  <SelectOption value={projectId}>{scopedProjectName}</SelectOption>
                ) : (
                  projects.map((project) => (
                    <SelectOption key={project.id} value={project.id}>
                      {project.name}
                    </SelectOption>
                  ))
                )}
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor="exploration-environment">环境</FieldLabel>
              <Select
                id="exploration-environment"
                placeholder="选择环境"
                setValue={(value) => setExplorationForm((current) => ({ ...current, environmentId: value }))}
                value={explorationForm.environmentId}
              >
                {availableEnvironments.map((environment) => (
                  <SelectOption key={environment.id} value={environment.id}>
                    {environment.name}
                  </SelectOption>
                ))}
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
            <Button onClick={() => setExplorationDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!canCreateExploration} onClick={saveExplorationRun} type="button">
              {editingExploration ? (
                "保存"
              ) : (
                <>
                  <Play className="size-4" />
                  创建任务
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}
