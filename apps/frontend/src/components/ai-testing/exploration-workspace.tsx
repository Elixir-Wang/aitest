"use client";

import { useEffect, useMemo, useState } from "react";

import type { ReactNode } from "react";

import { Eye, EyeOff, Play, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ListToolbar, PageShell, RowActions, ShellSection } from "@/components/ai-testing/page-shell";
import { TableLoadingRow } from "@/components/ai-testing/table-loading-row";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { type ApiProject, apiRequest, formatDateTime } from "@/lib/api-client";

type ProjectScope = "all" | "project";

type ProjectEnvironment = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  site_url: string;
  username: string;
  password_mask: string;
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
  description: string;
};

type ExplorationForm = {
  title: string;
  projectId: string;
  environmentId: string;
  scope: string;
  forbiddenPaths: string;
  loginStrategy: string;
  description: string;
};

const emptyForm: EnvironmentForm = {
  name: "",
  projectId: "",
  siteUrl: "",
  username: "",
  password: "",
  description: "",
};

const emptyExplorationForm: ExplorationForm = {
  title: "",
  projectId: "",
  environmentId: "",
  scope: "",
  forbiddenPaths: "",
  loginStrategy: "reuse_state",
  description: "",
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

export function ExplorationWorkspace({
  breadcrumbs,
  description,
  projectId,
  projectName = "",
  projectScope,
  title,
}: ExplorationWorkspaceProps) {
  const [activeTab, setActiveTab] = useState("探索任务");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [explorationDialogOpen, setExplorationDialogOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<ProjectEnvironment | null>(null);
  const [explorationLoading, setExplorationLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(true);
  const [projectLoading, setProjectLoading] = useState(projectScope === "all");
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [projects, setProjects] = useState<ApiProject[]>([]);
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
      if (projectScope === "project") {
        setProjectLoading(false);
        return;
      }

      setProjectLoading(true);
      try {
        const data = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(data);
          setForm((current) => ({ ...current, projectId: current.projectId || data[0]?.id || "" }));
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
        const path = projectScope === "project" && projectId ? `/projects/${projectId}/exploration-runs` : "/exploration-runs";
        const data = await apiRequest<ExplorationRun[]>(path);
        if (!ignore) {
          explorationSelection.setRows(data);
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
  }, [projectId, projectScope, explorationSelection.setRows]);

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

  const canCreateEnvironment = projectScope === "project" || form.projectId.length > 0;
  const selectedProjectId = projectScope === "project" ? (projectId ?? "") : explorationForm.projectId;
  const availableEnvironments = rows.filter((environment) => environment.project_id === selectedProjectId);
  const canCreateExploration = selectedProjectId.length > 0 && explorationForm.environmentId.length > 0;
  const environmentProjectSelectDisabled = [projectScope === "project", projectLoading, editingEnvironment !== null].some(Boolean);

  function openCreateDialog() {
    setEditingEnvironment(null);
    setForm({ ...emptyForm, projectId: projectId ?? "" });
    setShowPassword(false);
    setDialogOpen(true);
  }

  function openCreateExplorationDialog() {
    const targetProjectId = projectId ?? projects[0]?.id ?? "";
    const firstEnvironment = rows.find((environment) => environment.project_id === targetProjectId);
    setExplorationForm({
      ...emptyExplorationForm,
      projectId: targetProjectId,
      environmentId: firstEnvironment?.id ?? "",
    });
    setExplorationDialogOpen(true);
  }

  function openEditDialog(environment: ProjectEnvironment) {
    setEditingEnvironment(environment);
    setForm({
      name: environment.name,
      projectId: environment.project_id,
      siteUrl: environment.site_url,
      username: environment.username,
      password: "",
      description: environment.description,
    });
    setShowPassword(false);
    setDialogOpen(true);
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
          }
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
            description: form.description,
          }),
        });
        setRows((current) => [created, ...current]);
        toast.success("环境已创建");
      }
      setForm({ ...emptyForm, projectId: projectId ?? form.projectId });
      setDialogOpen(false);
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : editingEnvironment ? "环境更新失败" : "环境创建失败");
    }
  }

  async function createExplorationRun() {
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
      const created = await apiRequest<ExplorationRun>(`/projects/${targetProjectId}/exploration-runs`, {
        method: "POST",
        body: JSON.stringify({
          project_id: targetProjectId,
          environment_id: explorationForm.environmentId,
          title: explorationForm.title,
          scope: explorationForm.scope,
          forbidden_paths: explorationForm.forbiddenPaths,
          login_strategy: explorationForm.loginStrategy,
          description: explorationForm.description,
        }),
      });
      explorationSelection.setRows((current) => [created, ...current]);
      setExplorationDialogOpen(false);
      toast.success("探索任务已创建");
    } catch (requestError) {
      toast.error(requestError instanceof Error ? requestError.message : "探索任务创建失败");
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
      tabs={["探索任务", "环境配置", "探索文档", "候选需求文档", "冲突项"]}
      title={title}
      onTabChange={setActiveTab}
    >
      {activeTab === "探索任务" ? (
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
                  <TableHead>探索范围</TableHead>
                  <TableHead>创建时间</TableHead>
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
                    <TableCell className="font-medium">{item.title}</TableCell>
                    <TableCell>{item.project_name}</TableCell>
                    <TableCell>{item.environment_name}</TableCell>
                    <TableCell>{statusLabels[item.status] ?? item.status}</TableCell>
                    <TableCell>{loginStrategyLabels[item.login_strategy] ?? item.login_strategy}</TableCell>
                    <TableCell>
                      <span className="block max-w-64 truncate" title={item.scope}>
                        {item.scope || "-"}
                      </span>
                    </TableCell>
                    <TableCell>{formatDateTime(item.created_at)}</TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
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
                  <TableLoadingRow colSpan={10} label="探索任务加载中" />
                ) : null}
                {!explorationLoading && filteredExplorationRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={10}>
                      暂无探索任务数据
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      ) : null}

      {activeTab === "环境配置" ? (
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
                        <button
                          className="hover:underline"
                          onClick={() => openEditDialog(item)}
                          type="button"
                        >
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
                          actions={[{ label: "删除", icon: Trash2, destructive: true, onSelect: () => deleteEnvironments([item.id]) }]}
                          label={`打开 ${item.name} 操作菜单`}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {environmentLoading && filteredRows.length === 0 ? (
                    <TableLoadingRow colSpan={7} label="环境列表加载中" />
                  ) : null}
                </TableBody>
              </Table>
            </div>
          </ShellSection>
      ) : null}

      {["探索文档", "候选需求文档", "冲突项"].includes(activeTab) ? (
        <ShellSection>
          <div className="rounded-lg border p-8 text-center text-muted-foreground text-sm">
            {activeTab} 将在探索任务产生真实结果后展示。
          </div>
        </ShellSection>
      ) : null}

      <Dialog onOpenChange={setDialogOpen} open={dialogOpen}>
        <DialogContent className="gap-6 p-6 sm:max-w-3xl">
          <DialogHeader className="gap-3">
            <DialogTitle>{editingEnvironment ? "编辑环境" : "新建环境"}</DialogTitle>
            <DialogDescription>填写环境名称、所属项目、站点地址和登录信息，用于后续探索任务。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <LabeledInput
              id="environment-name"
              label="环境名称"
              onChange={(value) => setForm((current) => ({ ...current, name: value }))}
              placeholder="测试环境"
              value={form.name}
            />
            <div className="space-y-2">
              <label className="font-medium text-sm" htmlFor="environment-project">
                项目
              </label>
              <Select
                disabled={environmentProjectSelectDisabled}
                onValueChange={(value) => setForm((current) => ({ ...current, projectId: value }))}
                value={projectScope === "project" ? projectId : form.projectId}
              >
                <SelectTrigger className="w-full" id="environment-project">
                  <SelectValue placeholder={projectScope === "project" ? projectName : "选择项目"} />
                </SelectTrigger>
                <SelectContent>
                  {projectScope === "project" && projectId ? (
                    <SelectItem value={projectId}>{projectName}</SelectItem>
                  ) : (
                    projects.map((project) => (
                      <SelectItem key={project.id} value={project.id}>
                        {project.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <LabeledInput
              id="environment-site-url"
              label="站点地址"
              onChange={(value) => setForm((current) => ({ ...current, siteUrl: value }))}
              placeholder="https://test.example.com"
              value={form.siteUrl}
            />
            <LabeledInput
              id="environment-username"
              label="用户名"
              onChange={(value) => setForm((current) => ({ ...current, username: value }))}
              placeholder="tester"
              value={form.username}
            />
            <LabeledInput
              id="environment-password"
              label={editingEnvironment ? "密码（留空表示不修改）" : "密码"}
              onChange={(value) => setForm((current) => ({ ...current, password: value }))}
              placeholder={editingEnvironment ? "留空表示不修改密码" : "请输入密码"}
              trailing={
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
              }
              type={showPassword ? "text" : "password"}
              value={form.password}
            />
            <div className="space-y-2 sm:col-span-2">
              <label className="font-medium text-sm" htmlFor="environment-description">
                描述
              </label>
              <Textarea
                className="min-h-28"
                id="environment-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="账号权限、验证码处理方式、探索范围或注意事项"
                value={form.description}
              />
            </div>
          </div>
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

      <Dialog onOpenChange={setExplorationDialogOpen} open={explorationDialogOpen}>
        <DialogContent className="gap-6 p-6 sm:max-w-3xl">
          <DialogHeader className="gap-3">
            <DialogTitle>新建探索任务</DialogTitle>
            <DialogDescription>选择环境并配置探索范围、禁止路径和登录策略。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-x-6 gap-y-5 sm:grid-cols-2">
            <LabeledInput
              id="exploration-title"
              label="任务名称"
              onChange={(value) => setExplorationForm((current) => ({ ...current, title: value }))}
              placeholder="后台管理系统全站探索"
              value={explorationForm.title}
            />
            <div className="space-y-2">
              <label className="font-medium text-sm" htmlFor="exploration-project">
                项目
              </label>
              <Select
                disabled={projectScope === "project" || projectLoading}
                onValueChange={(value) => {
                  const firstEnvironment = rows.find((environment) => environment.project_id === value);
                  setExplorationForm((current) => ({
                    ...current,
                    projectId: value,
                    environmentId: firstEnvironment?.id ?? "",
                  }));
                }}
                value={projectScope === "project" ? projectId : explorationForm.projectId}
              >
                <SelectTrigger className="w-full" id="exploration-project">
                  <SelectValue placeholder={projectScope === "project" ? projectName : "选择项目"} />
                </SelectTrigger>
                <SelectContent>
                  {projectScope === "project" && projectId ? (
                    <SelectItem value={projectId}>{projectName}</SelectItem>
                  ) : (
                    projects.map((project) => (
                      <SelectItem key={project.id} value={project.id}>
                        {project.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="font-medium text-sm" htmlFor="exploration-environment">
                环境
              </label>
              <Select
                onValueChange={(value) => setExplorationForm((current) => ({ ...current, environmentId: value }))}
                value={explorationForm.environmentId}
              >
                <SelectTrigger className="w-full" id="exploration-environment">
                  <SelectValue placeholder="选择环境" />
                </SelectTrigger>
                <SelectContent>
                  {availableEnvironments.map((environment) => (
                    <SelectItem key={environment.id} value={environment.id}>
                      {environment.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="font-medium text-sm" htmlFor="exploration-login-strategy">
                登录策略
              </label>
              <Select
                onValueChange={(value) => setExplorationForm((current) => ({ ...current, loginStrategy: value }))}
                value={explorationForm.loginStrategy}
              >
                <SelectTrigger className="w-full" id="exploration-login-strategy">
                  <SelectValue placeholder="选择登录策略" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(loginStrategyLabels).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="font-medium text-sm" htmlFor="exploration-scope">
                探索范围
              </label>
              <Textarea
                className="min-h-24"
                id="exploration-scope"
                onChange={(event) => setExplorationForm((current) => ({ ...current, scope: event.target.value }))}
                placeholder="菜单范围、URL 白名单、核心模块标记"
                value={explorationForm.scope}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="font-medium text-sm" htmlFor="exploration-forbidden-paths">
                禁止路径
              </label>
              <Textarea
                className="min-h-20"
                id="exploration-forbidden-paths"
                onChange={(event) =>
                  setExplorationForm((current) => ({ ...current, forbiddenPaths: event.target.value }))
                }
                placeholder="删除、支付、外发、批量通知等危险路径"
                value={explorationForm.forbiddenPaths}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="font-medium text-sm" htmlFor="exploration-description">
                描述
              </label>
              <Textarea
                className="min-h-20"
                id="exploration-description"
                onChange={(event) => setExplorationForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="本次探索目标、角色说明、验证码处理方式或人工注意事项"
                value={explorationForm.description}
              />
            </div>
          </div>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setExplorationDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button disabled={!canCreateExploration} onClick={createExplorationRun} type="button">
              <Play className="size-4" />
              创建任务
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageShell>
  );
}

function LabeledInput({
  id,
  label,
  onChange,
  placeholder,
  trailing,
  type = "text",
  value,
}: {
  id: string;
  label: string;
  onChange: (value: string) => void;
  placeholder: string;
  trailing?: ReactNode;
  type?: string;
  value: string;
}) {
  const hasTrailing = trailing !== undefined && trailing !== null;

  return (
    <div className="space-y-2">
      <label className="font-medium text-sm" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <Input
          className={hasTrailing ? "pr-10" : undefined}
          id={id}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          type={type}
          value={value}
        />
        {trailing}
      </div>
    </div>
  );
}
