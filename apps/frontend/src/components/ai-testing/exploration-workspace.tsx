"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import { CircleHelp, Eye, EyeOff, LogIn, Plus, Save, Square, Trash2, X } from "lucide-react";
import { toast } from "@/lib/toast";

import {
  authStateStatusLabels,
  captchaStrategyLabels,
  captchaStrategyOptions,
  type EnvironmentForm,
  emptyEnvironmentForm,
  environmentLoginStrategyOptions,
  explorationStatusLabels,
  formatAuthStateExpiresAt,
  formatAuthStateTimeRemaining,
  formFromEnvironment,
  formMatchesSavedManualAuthConfig,
  isActiveManualAuthSession,
  isAiLetterAutoAuthEnabled,
  isManualAuthEnabled,
  isManualAuthSessionEnded,
  isMissingManualAuthSessionError,
  loginStrategyLabels,
  type ManualAuthSession,
  reuseAuthStateLabels,
  reuseAuthStateOptions,
} from "@/components/ai-testing/exploration-environment-utils";
import { ExplorationEnvironmentsTable } from "@/components/ai-testing/exploration-environments-table";
import {
  type ExplorationPageRecord,
  ExplorationProjectPagesTree,
} from "@/components/ai-testing/exploration-project-pages-tree";
import { ExplorationRunsTable } from "@/components/ai-testing/exploration-runs-table";
import { IllustratedEmptyState } from "@/components/ai-testing/illustrated-empty-state";
import { ListToolbar, type PageBreadcrumb, PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { useLocalTableSelection } from "@/components/ai-testing/use-local-table-selection";
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { type ApiProject, apiRequest } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";
import type {
  ExplorationEnvironment,
  ExplorationRunSummary as ExplorationRun,
  ProjectScope,
} from "@/lib/exploration-types";

type ProjectArtifactRow = {
  project_id: string;
  project_name: string;
};

type ExplorationWorkspaceProps = {
  breadcrumbs: PageBreadcrumb[];
  description: string;
  projectId?: string;
  projectScope: ProjectScope;
  title: string;
};

const explorationTabs = ["探索列表", "探索环境", "探索产物"];
export function ExplorationWorkspace({
  breadcrumbs,
  description,
  projectId,
  projectScope,
  title,
}: ExplorationWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const createParamHandledRef = useRef(false);
  const authStateToastRef = useRef<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState("探索列表");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<ExplorationEnvironment | null>(null);
  const [manualAuthSession, setManualAuthSession] = useState<ManualAuthSession | null>(null);
  const [manualAuthAction, setManualAuthAction] = useState<"cancel" | "save" | "start" | "">("");
  const [stoppingExploration, setStoppingExploration] = useState<ExplorationRun | null>(null);
  const [stoppingExplorationId, setStoppingExplorationId] = useState("");
  const [startingExplorationId, setStartingExplorationId] = useState("");
  const [explorationLoading, setExplorationLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [form, setForm] = useState<EnvironmentForm>({ ...emptyEnvironmentForm });
  const [selectedArtifactProjectId, setSelectedArtifactProjectId] = useState("");
  const [projectPages, setProjectPages] = useState<ExplorationPageRecord[]>([]);
  const [projectPagesLoading, setProjectPagesLoading] = useState(false);
  const [selectedPageId, setSelectedPageId] = useState("");
  const [expandedPageNodeIds, setExpandedPageNodeIds] = useState<string[]>([]);
  const [clearArtifactsDialogOpen, setClearArtifactsDialogOpen] = useState(false);
  const [clearingArtifacts, setClearingArtifacts] = useState(false);
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
  } = useLocalTableSelection<ExplorationEnvironment>([]);
  useEffect(() => {
    let ignore = false;

    async function loadProjects() {
      try {
        const data = await apiRequest<ApiProject[]>("/projects");
        if (!ignore) {
          setProjects(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError instanceof Error ? requestError.message : "项目列表加载失败");
        }
      }
    }

    void loadProjects();

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    let ignore = false;

    async function loadEnvironments() {
      setEnvironmentLoading(true);
      setError("");
      try {
        const environmentsPath = projectId ? `/environments?project_id=${projectId}` : "/environments";
        const data = await apiRequest<ExplorationEnvironment[]>(environmentsPath);
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
  }, [projectId, setRows]);

  const hasLoggingInEnvironment = useMemo(() => rows.some((item) => item.auth_state_status === "logging_in"), [rows]);

  useEffect(() => {
    if (!hasLoggingInEnvironment) {
      return;
    }

    let ignore = false;
    const environmentsPath = projectId ? `/environments?project_id=${projectId}` : "/environments";

    async function refreshEnvironmentAuthStates() {
      try {
        const data = await apiRequest<ExplorationEnvironment[]>(environmentsPath);
        if (ignore) {
          return;
        }
        for (const item of data) {
          const previous = authStateToastRef.current[item.id];
          if (previous === "logging_in" && item.auth_state_status === "valid") {
            toast.success("登录态已自动保存");
          } else if (previous === "logging_in" && item.auth_state_status === "login_failed") {
            toast.error(item.auth_state_message || "自动登录失败");
          }
          authStateToastRef.current[item.id] = item.auth_state_status;
        }
        setRows(data);
      } catch {
        // ignore polling errors
      }
    }

    void refreshEnvironmentAuthStates();
    const intervalId = window.setInterval(() => {
      void refreshEnvironmentAuthStates();
    }, 2000);

    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, [hasLoggingInEnvironment, projectId, setRows]);

  useEffect(() => {
    let ignore = false;

    async function loadExplorationRuns() {
      setExplorationLoading(true);
      setError("");
      try {
        const path =
          projectScope === "project" && projectId
            ? `/page-exploration/runs?project_id=${projectId}`
            : "/page-exploration/runs-all";
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

  const loadProjectPages = useCallback(async (project: ProjectArtifactRow) => {
    setProjectPagesLoading(true);
    setProjectPages([]);
    setSelectedPageId("");
    setExpandedPageNodeIds([]);
    try {
      const pages = await apiRequest<ExplorationPageRecord[]>(`/page-exploration/projects/${project.project_id}/pages`);
      setProjectPages(pages);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索页面加载失败",
        actionLabel: "加载探索页面",
        method: "GET",
        path: `/page-exploration/projects/${project.project_id}/pages`,
      });
    } finally {
      setProjectPagesLoading(false);
    }
  }, []);

  const filteredRows = useMemo(
    () =>
      rows.filter((item) =>
        [
          item.name,
          item.project_name,
          item.site_url,
          item.username,
          loginStrategyLabels[item.login_strategy] ?? item.login_strategy,
          captchaStrategyLabels[item.captcha_strategy] ?? item.captcha_strategy,
          authStateStatusLabels[item.auth_state_status] ?? item.auth_state_status,
          item.updated_at,
        ].some((value) => (value ?? "").toLowerCase().includes(searchText.trim().toLowerCase())),
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
          item.requirement_doc_title,
          explorationStatusLabels[item.status] ?? item.status,
          item.scope,
          item.goal,
          item.notes,
          item.updated_at,
        ].some((value) => (value ?? "").toLowerCase().includes(searchText.trim().toLowerCase())),
      ),
    [explorationSelection.rows, searchText],
  );

  const artifactProjectOptions = useMemo(() => {
    const visibleProjects = projectId ? projects.filter((project) => project.id === projectId) : projects;
    return visibleProjects
      .filter((project) => project.status !== "archived")
      .map((project): ProjectArtifactRow => ({ project_id: project.id, project_name: project.name }));
  }, [projectId, projects]);

  useEffect(() => {
    if (activeTab !== "探索产物") {
      return;
    }

    if (artifactProjectOptions.length === 0) {
      setSelectedArtifactProjectId("");
      setProjectPages([]);
      setSelectedPageId("");
      setExpandedPageNodeIds([]);
      return;
    }

    if (!artifactProjectOptions.some((item) => item.project_id === selectedArtifactProjectId)) {
      setSelectedArtifactProjectId(artifactProjectOptions[0].project_id);
    }
  }, [activeTab, artifactProjectOptions, selectedArtifactProjectId]);

  const selectedArtifactProject =
    artifactProjectOptions.find((item) => item.project_id === selectedArtifactProjectId) ??
    artifactProjectOptions[0] ??
    null;

  const canClearArtifacts = Boolean(selectedArtifactProject) && !projectPagesLoading && !clearingArtifacts;

  useEffect(() => {
    if (activeTab !== "探索产物" || !selectedArtifactProject) {
      return;
    }

    void loadProjectPages(selectedArtifactProject);
  }, [activeTab, loadProjectPages, selectedArtifactProject]);

  async function clearProjectArtifacts() {
    if (!selectedArtifactProject) {
      return;
    }
    setClearingArtifacts(true);
    try {
      await apiRequest(`/page-exploration/projects/${selectedArtifactProject.project_id}/artifacts`, {
        method: "DELETE",
      });
      setProjectPages([]);
      setSelectedPageId("");
      setExpandedPageNodeIds([]);
      setClearArtifactsDialogOpen(false);
      toast.success("探索产物已清空");
      await loadProjectPages(selectedArtifactProject);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索产物清空失败",
        actionLabel: "清空探索产物",
        method: "DELETE",
        path: `/page-exploration/projects/${selectedArtifactProject.project_id}/artifacts`,
      });
    } finally {
      setClearingArtifacts(false);
    }
  }

  const hasReusableEnvironmentPassword =
    editingEnvironment?.login_strategy === "account_password" && editingEnvironment.has_saved_credentials;
  const canCreateEnvironment =
    form.projectId.length > 0 &&
    form.name.trim().length > 0 &&
    form.siteUrl.trim().length > 0 &&
    (form.loginStrategy !== "account_password" ||
      (form.username.trim().length > 0 && (hasReusableEnvironmentPassword || form.password.trim().length > 0)));
  const showLoginCredentials = form.loginStrategy === "account_password";
  const availableCaptchaStrategyOptions = form.reuseAuthState
    ? captchaStrategyOptions
    : captchaStrategyOptions.filter((value) => value !== "manual");
  const selectedAuthStateStatus =
    manualAuthSession?.auth_state_status ?? editingEnvironment?.auth_state_status ?? "none";
  const selectedAuthStateExpiresAt =
    manualAuthSession?.auth_state_expires_at ?? editingEnvironment?.auth_state_expires_at ?? null;
  const selectedManualCaptcha = showLoginCredentials && form.captchaStrategy === "manual";
  const selectedAiLetterCaptcha = showLoginCredentials && form.captchaStrategy === "ai_letter";
  const savedManualAuthEnabled = isManualAuthEnabled(editingEnvironment);
  const savedAiLetterAutoAuthEnabled = isAiLetterAutoAuthEnabled(editingEnvironment);
  const showManualAuthControls =
    savedManualAuthEnabled && selectedManualCaptcha && formMatchesSavedManualAuthConfig(editingEnvironment, form);
  const showAiLetterAutoAuthStatus =
    savedAiLetterAutoAuthEnabled &&
    selectedAiLetterCaptcha &&
    form.reuseAuthState &&
    form.loginStrategy === "account_password" &&
    form.captchaStrategy === "ai_letter";
  const manualAuthSessionActive = isActiveManualAuthSession(manualAuthSession);
  const authStateSummaryLabel =
    {
      expired: "登录态已过期",
      login_failed: "登录态获取失败",
      logging_in: "正在获取登录态",
      none: "暂无登录态",
      unknown: "登录态未检测",
      valid: "登录态有效",
    }[selectedAuthStateStatus] ?? `登录态${authStateStatusLabels[selectedAuthStateStatus] ?? selectedAuthStateStatus}`;
  const authStateAccentClassName =
    selectedAuthStateStatus === "valid"
      ? "before:bg-emerald-500"
      : selectedAuthStateStatus === "expired" || selectedAuthStateStatus === "login_failed"
        ? "before:bg-red-500"
        : selectedAuthStateStatus === "unknown"
          ? "before:bg-amber-500"
          : selectedAuthStateStatus === "logging_in"
            ? "before:bg-blue-500"
            : "before:bg-muted-foreground/40";

  const syncManualAuthState = useCallback(
    (session: ManualAuthSession, environmentId: string) => {
      setEditingEnvironment((current) =>
        current && current.id === environmentId
          ? {
              ...current,
              auth_state_status: session.auth_state_status,
              auth_state_expires_at: session.auth_state_expires_at,
              has_saved_credentials: session.has_saved_credentials,
            }
          : current,
      );
      setRows((current) =>
        current.map((row) =>
          row.id === environmentId
            ? {
                ...row,
                auth_state_status: session.auth_state_status,
                auth_state_expires_at: session.auth_state_expires_at,
                has_saved_credentials: session.has_saved_credentials,
              }
            : row,
        ),
      );
    },
    [setRows],
  );

  const completeManualAuthSession = useCallback(
    (session: ManualAuthSession, environmentId: string) => {
      setManualAuthSession(null);
      syncManualAuthState(session, environmentId);
      if (session.status === "auto_saved") {
        toast.success(session.message || "登录态已自动保存");
      }
    },
    [syncManualAuthState],
  );

  useEffect(() => {
    if (!editingEnvironment || !manualAuthSessionActive || !manualAuthSession) {
      return;
    }

    let ignore = false;
    const environmentId = editingEnvironment.id;
    const statusPath = `/environments/${environmentId}/manual-auth/${manualAuthSession.session_id}/status`;

    async function refreshManualAuthStatus() {
      try {
        const session = await apiRequest<ManualAuthSession>(statusPath);
        if (ignore) {
          return;
        }
        if (isManualAuthSessionEnded(session)) {
          completeManualAuthSession(session, environmentId);
          return;
        }
        setManualAuthSession(session);
      } catch (requestError) {
        if (!ignore && isMissingManualAuthSessionError(requestError)) {
          setManualAuthSession(null);
        }
      }
    }

    void refreshManualAuthStatus();
    const intervalId = window.setInterval(() => {
      void refreshManualAuthStatus();
    }, 750);

    return () => {
      ignore = true;
      window.clearInterval(intervalId);
    };
  }, [completeManualAuthSession, editingEnvironment, manualAuthSession, manualAuthSessionActive]);

  function openCreateDialog() {
    setEditingEnvironment(null);
    setManualAuthSession(null);
    setManualAuthAction("");
    setForm({ ...emptyEnvironmentForm, projectId: projectId ?? "" });
    setShowPassword(false);
    setDialogOpen(true);
  }

  const openCreateExplorationDialog = useCallback(() => {
    router.push(projectId ? `/projects/${projectId}/exploration/new` : "/exploration/new");
  }, [projectId, router]);

  useEffect(() => {
    if (searchParams.get("create") !== "exploration" || createParamHandledRef.current) {
      return;
    }

    createParamHandledRef.current = true;
    setActiveTab("探索列表");
    openCreateExplorationDialog();
  }, [openCreateExplorationDialog, searchParams]);

  function openEditDialog(environment: ExplorationEnvironment) {
    setEditingEnvironment(environment);
    setManualAuthSession(null);
    setManualAuthAction("");
    setForm(formFromEnvironment(environment));
    setShowPassword(false);
    setDialogOpen(true);
  }

  function setReuseAuthStateValue(value: string) {
    const reuseAuthState = value === "enabled";
    if (!reuseAuthState && form.captchaStrategy === "manual") {
      void cancelManualAuth(false);
      setManualAuthSession(null);
    }
    setForm((current) => ({
      ...current,
      captchaStrategy: reuseAuthState || current.captchaStrategy !== "manual" ? current.captchaStrategy : "none",
      reuseAuthState,
    }));
  }

  function setCaptchaStrategyValue(value: string) {
    if (value !== "manual") {
      void cancelManualAuth(false);
      setManualAuthSession(null);
    }
    setForm((current) => ({ ...current, captchaStrategy: value }));
  }

  function handleEnvironmentDialogOpenChange(open: boolean) {
    setDialogOpen(open);
    if (!open) {
      void cancelManualAuth(false);
      setEditingEnvironment(null);
      setManualAuthSession(null);
      setManualAuthAction("");
      setShowPassword(false);
      setForm({ ...emptyEnvironmentForm });
    }
  }

  function openEditExplorationDialog(run: ExplorationRun) {
    router.push(`/projects/${run.project_id}/exploration/${run.id}/edit`);
  }

  async function saveEnvironment() {
    if (!form.projectId || !form.name.trim() || !form.siteUrl.trim()) {
      toast.error("请选择项目并填写环境名称和站点地址");
      return;
    }

    try {
      const normalizedCaptchaStrategy =
        showLoginCredentials && form.captchaStrategy !== "manual"
          ? form.captchaStrategy
          : showLoginCredentials && form.reuseAuthState
            ? form.captchaStrategy
            : "none";
      const normalizedReuseAuthState = showLoginCredentials ? form.reuseAuthState : false;
      if (editingEnvironment) {
        // 更新环境
        const payload: Record<string, boolean | string> = {
          name: form.name,
          site_url: form.siteUrl,
          username: showLoginCredentials ? form.username : "",
          login_strategy: form.loginStrategy,
          captcha_strategy: normalizedCaptchaStrategy,
          reuse_auth_state: normalizedReuseAuthState,
          description: form.description,
        };
        // 只有填写了密码才更新密码
        if (showLoginCredentials && form.password) {
          payload.password = form.password;
        }

        const updated = await apiRequest<ExplorationEnvironment>(`/environments/${editingEnvironment.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        setEditingEnvironment(updated);
        setForm(formFromEnvironment(updated));
        if (isManualAuthEnabled(updated)) {
          setManualAuthSession(null);
          toast.success("环境已更新，可打开登录窗口保存登录态");
          return;
        }
        if (isAiLetterAutoAuthEnabled(updated)) {
          if (updated.auth_state_status === "logging_in") {
            authStateToastRef.current[updated.id] = updated.auth_state_status;
            notifyAiTaskStarted();
            toast.success("环境已更新，正在自动登录…");
            handleEnvironmentDialogOpenChange(false);
            return;
          }
          toast.success("环境已更新");
          handleEnvironmentDialogOpenChange(false);
          return;
        }
        toast.success("环境已更新");
      } else {
        // 创建环境
        const created = await apiRequest<ExplorationEnvironment>("/environments", {
          method: "POST",
          body: JSON.stringify({
            project_id: form.projectId,
            name: form.name,
            site_url: form.siteUrl,
            username: showLoginCredentials ? form.username : "",
            password: showLoginCredentials ? form.password : "",
            login_strategy: form.loginStrategy,
            captcha_strategy: normalizedCaptchaStrategy,
            reuse_auth_state: normalizedReuseAuthState,
            description: form.description,
          }),
        });
        setRows((current) => [created, ...current]);
        if (isManualAuthEnabled(created)) {
          setEditingEnvironment(created);
          setForm(formFromEnvironment(created));
          toast.success("环境已创建，可打开登录窗口保存登录态");
          return;
        }
        if (isAiLetterAutoAuthEnabled(created)) {
          authStateToastRef.current[created.id] = created.auth_state_status;
          notifyAiTaskStarted();
          toast.success("环境已创建，正在自动登录…");
          handleEnvironmentDialogOpenChange(false);
          return;
        }
        toast.success("环境已创建");
      }
      handleEnvironmentDialogOpenChange(false);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: editingEnvironment ? "环境更新失败" : "环境创建失败",
        actionLabel: editingEnvironment ? "更新环境" : "创建环境",
        method: editingEnvironment ? "PATCH" : "POST",
        path: editingEnvironment ? `/environments/${editingEnvironment.id}` : "/environments",
      });
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
          return apiRequest(`/page-exploration/runs/${id}`, { method: "DELETE" });
        }),
      );
      explorationSelection.setRows((current) => current.filter((row) => !ids.includes(row.id)));
      explorationSelection.clearSelection();
      toast.success(`已删除 ${ids.length} 个探索任务`);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索任务删除失败",
        actionLabel: "删除探索任务",
        method: "DELETE",
        path: "/projects/{projectId}/exploration-runs/{runId}",
      });
    }
  }

  async function stopExplorationRun(run: ExplorationRun) {
    setStoppingExplorationId(run.id);
    try {
      const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${run.id}/stop`, {
        method: "POST",
      });
      explorationSelection.setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      toast.success("探索任务已停止");
      setStoppingExploration(null);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索任务停止失败",
        actionLabel: "停止探索任务",
        method: "POST",
        path: `/page-exploration/runs/${run.id}/stop`,
      });
    } finally {
      setStoppingExplorationId("");
    }
  }

  async function startExplorationRun(run: ExplorationRun) {
    setStartingExplorationId(run.id);
    try {
      const updated = await apiRequest<ExplorationRun>(`/page-exploration/runs/${run.id}/start`, {
        method: "POST",
      });
      explorationSelection.setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      notifyAiTaskStarted();
      toast.success(run.status === "pending" ? "探索任务已开始" : "重新探索已开始");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "探索任务启动失败",
        actionLabel: run.status === "pending" ? "启动探索任务" : "重新探索",
        method: "POST",
        path: `/page-exploration/runs/${run.id}/start`,
      });
    } finally {
      setStartingExplorationId("");
    }
  }

  async function startAiLetterAutoAuth(environment: ExplorationEnvironment) {
    if (environment.auth_state_status === "logging_in") {
      return;
    }
    try {
      const updated = await apiRequest<ExplorationEnvironment>(`/environments/${environment.id}/auto-auth/start`, {
        method: "POST",
      });
      setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      if (editingEnvironment?.id === updated.id) {
        setEditingEnvironment(updated);
      }
      authStateToastRef.current[updated.id] = updated.auth_state_status;
      notifyAiTaskStarted();
      toast.success("正在自动登录…");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "自动登录启动失败",
        actionLabel: "环境登录",
        method: "POST",
        path: `/environments/${environment.id}/auto-auth/start`,
      });
    }
  }

  async function startManualAuth() {
    if (!editingEnvironment) {
      return;
    }
    setManualAuthAction("start");
    try {
      const session = await apiRequest<ManualAuthSession>(`/environments/${editingEnvironment.id}/manual-auth/start`, {
        method: "POST",
      });
      setManualAuthSession(session);
      toast.success(session.message || "登录窗口已打开");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "打开人工登录窗口失败",
        actionLabel: "打开人工登录窗口",
        method: "POST",
        path: `/environments/${editingEnvironment.id}/manual-auth/start`,
      });
    } finally {
      setManualAuthAction("");
    }
  }

  async function saveManualAuth() {
    if (!editingEnvironment || !manualAuthSession) {
      return;
    }
    setManualAuthAction("save");
    try {
      const result = await apiRequest<ManualAuthSession>(
        `/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/save`,
        { method: "POST" },
      );
      if (result.status === "ended") {
        completeManualAuthSession(result, editingEnvironment.id);
        return;
      }
      setManualAuthSession(result);
      syncManualAuthState(result, editingEnvironment.id);
      setManualAuthSession(null);
      toast.success(result.message || "登录态已保存");
    } catch (requestError) {
      if (isMissingManualAuthSessionError(requestError)) {
        setManualAuthSession(null);
        return;
      }
      reportError(requestError, {
        fallbackMessage: "保存登录态失败",
        actionLabel: "保存人工登录态",
        method: "POST",
        path: `/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/save`,
      });
    } finally {
      setManualAuthAction("");
    }
  }

  async function cancelManualAuth(showToast = true) {
    if (!editingEnvironment || !manualAuthSession) {
      return;
    }
    setManualAuthAction("cancel");
    try {
      const result = await apiRequest<ManualAuthSession>(
        `/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/cancel`,
        { method: "POST" },
      );
      setManualAuthSession(null);
      syncManualAuthState(result, editingEnvironment.id);
      if (showToast && result.status !== "ended") {
        toast.success(result.message || "人工登录会话已取消");
      }
    } catch (requestError) {
      if (isMissingManualAuthSessionError(requestError)) {
        setManualAuthSession(null);
        return;
      }
      if (showToast) {
        reportError(requestError, {
          fallbackMessage: "取消人工登录失败",
          actionLabel: "取消人工登录会话",
          method: "POST",
          path: `/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/cancel`,
        });
      }
    } finally {
      setManualAuthAction("");
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
          return apiRequest(`/environments/${id}`, { method: "DELETE" });
        }),
      );
      setRows((current) => current.filter((row) => !ids.includes(row.id)));
      clearSelection();
      toast.success(`已删除 ${ids.length} 个环境`);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "环境删除失败",
        actionLabel: "删除环境",
        method: "DELETE",
        path: "/environments/{environmentId}",
      });
    }
  }

  return (
    <PageShell
      activeTab={activeTab}
      breadcrumbs={breadcrumbs}
      description={description}
      projectScope={projectScope}
      tabActions={
        activeTab === "探索产物" ? (
          <Button
            disabled={!canClearArtifacts}
            onClick={() => setClearArtifactsDialogOpen(true)}
            size="sm"
            type="button"
            variant="outline"
          >
            <Trash2 className="size-4" />
            清空产物
          </Button>
        ) : null
      }
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
          <ExplorationRunsTable
            allSelected={explorationSelection.allSelected}
            loading={explorationLoading}
            onDelete={deleteExplorationRuns}
            onEdit={openEditExplorationDialog}
            onOpen={openExplorationRun}
            onStart={(run) => void startExplorationRun(run)}
            onStop={setStoppingExploration}
            onToggleAll={explorationSelection.toggleAll}
            onToggleOne={explorationSelection.toggleOne}
            partiallySelected={explorationSelection.partiallySelected}
            rows={filteredExplorationRows}
            selectedIds={explorationSelection.selectedIds}
            startingExplorationId={startingExplorationId}
          />
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
            placeholder="搜索环境名称、站点或用户名"
            selectedCount={selectedCount}
            title="环境列表"
          />
          <ExplorationEnvironmentsTable
            allSelected={allSelected}
            loading={environmentLoading}
            onDelete={deleteEnvironments}
            onEdit={openEditDialog}
            onStartAiLetterAutoAuth={(environment) => void startAiLetterAutoAuth(environment)}
            onToggleAll={toggleAll}
            onToggleOne={toggleOne}
            partiallySelected={partiallySelected}
            rows={filteredRows}
            selectedIds={selectedIds}
          />
        </ShellSection>
      ) : null}

      {activeTab === "探索产物" ? (
        <ShellSection>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-medium text-sm">项目列表</h2>
            <div className="flex items-center gap-3">
              <span className="font-medium text-muted-foreground text-sm">项目</span>
              <Select
                className="w-auto min-w-28"
                disabled={artifactProjectOptions.length === 0}
                placeholder="选择项目"
                setValue={setSelectedArtifactProjectId}
                value={selectedArtifactProject?.project_id ?? ""}
              >
                {artifactProjectOptions.map((artifact) => (
                  <SelectOption key={artifact.project_id} value={artifact.project_id}>
                    {artifact.project_name}
                  </SelectOption>
                ))}
              </Select>
            </div>
          </div>
          {artifactProjectOptions.length === 0 ? (
            <IllustratedEmptyState
              className="rounded-lg border"
              description="创建项目后，可在这里查看页面探索产物。"
              title="暂无可切换项目"
            />
          ) : null}
          {selectedArtifactProject ? (
            <div>
              <ExplorationProjectPagesTree
                expandedNodeIds={expandedPageNodeIds}
                loading={projectPagesLoading}
                onPageSelect={setSelectedPageId}
                onToggleNode={(nodeId) =>
                  setExpandedPageNodeIds((ids) =>
                    ids.includes(nodeId) ? ids.filter((id) => id !== nodeId) : [...ids, nodeId],
                  )
                }
                pages={projectPages}
                projectId={selectedArtifactProject.project_id}
                selectedPageId={selectedPageId}
              />
            </div>
          ) : null}
        </ShellSection>
      ) : null}

      <Dialog onOpenChange={setClearArtifactsDialogOpen} open={clearArtifactsDialogOpen}>
        <DialogContent className="gap-5 p-6 sm:max-w-md">
          <DialogHeader className="gap-3">
            <DialogTitle>清空探索产物</DialogTitle>
            <DialogDescription>将清空当前项目的页面 YAML、页面目录和报告索引，探索任务记录会保留。</DialogDescription>
          </DialogHeader>
          <DialogFooter className="-mx-6 -mb-6 px-6 py-4">
            <Button onClick={() => setClearArtifactsDialogOpen(false)} type="button" variant="outline">
              取消
            </Button>
            <Button
              disabled={clearingArtifacts}
              onClick={() => void clearProjectArtifacts()}
              type="button"
              variant="destructive"
            >
              <Trash2 className="size-4" />
              清空产物
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog onOpenChange={handleEnvironmentDialogOpenChange} open={dialogOpen}>
        <DialogContent className="gap-0 p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>{editingEnvironment ? "编辑环境" : "新建环境"}</DialogTitle>
          </DialogHeader>
          <FieldGroup className="grid gap-x-6 gap-y-5 px-6 py-5 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="environment-name">环境名称 *</FieldLabel>
              <Input
                aria-required="true"
                id="environment-name"
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="业务环境"
                required
                value={form.name}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-project">所属项目 *</FieldLabel>
              <Select
                disabled={Boolean(editingEnvironment) || Boolean(projectId)}
                id="environment-project"
                placeholder="选择项目"
                setValue={(value) => setForm((current) => ({ ...current, projectId: value }))}
                value={form.projectId}
              >
                {projects
                  .filter((project) => project.status !== "archived")
                  .map((project) => (
                    <SelectOption key={project.id} value={project.id}>
                      {project.name}
                    </SelectOption>
                  ))}
              </Select>
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="environment-site-url">站点地址 *</FieldLabel>
              <Input
                aria-required="true"
                id="environment-site-url"
                onChange={(event) => setForm((current) => ({ ...current, siteUrl: event.target.value }))}
                placeholder="https://test.example.com"
                required
                value={form.siteUrl}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="environment-login-strategy">登录策略</FieldLabel>
              <Select
                id="environment-login-strategy"
                placeholder="选择登录策略"
                setValue={(value) => {
                  if (value === "skip_login") {
                    void cancelManualAuth(false);
                    setManualAuthSession(null);
                  }
                  setForm((current) => ({
                    ...current,
                    loginStrategy: value,
                    captchaStrategy: value === "skip_login" ? "none" : current.captchaStrategy,
                    password: value === "skip_login" ? "" : current.password,
                    reuseAuthState: value === "skip_login" ? false : current.reuseAuthState,
                    username: value === "skip_login" ? "" : current.username,
                  }));
                }}
                value={form.loginStrategy}
              >
                {environmentLoginStrategyOptions.map((value) => (
                  <SelectOption key={value} value={value}>
                    {loginStrategyLabels[value]}
                  </SelectOption>
                ))}
              </Select>
            </Field>
            {showLoginCredentials ? (
              <>
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
                  <FieldLabel htmlFor="environment-password">
                    {hasReusableEnvironmentPassword ? "密码（留空表示不修改）" : "密码"}
                  </FieldLabel>
                  <div className="relative">
                    <Input
                      className="pr-9"
                      id="environment-password"
                      onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                      placeholder={hasReusableEnvironmentPassword ? "留空表示不修改密码" : "请输入密码"}
                      type={showPassword ? "text" : "password"}
                      value={form.password}
                    />
                    <Button
                      aria-label={showPassword ? "隐藏密码" : "显示密码"}
                      className="absolute top-0 right-0"
                      onClick={() => setShowPassword((current) => !current)}
                      size="icon"
                      type="button"
                      variant="ghost"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </Button>
                  </div>
                </Field>
                <div className="grid gap-x-6 gap-y-5 sm:col-span-2 sm:grid-cols-2">
                  <Field>
                    <div className="flex items-center gap-1.5">
                      <FieldLabel htmlFor="environment-reuse-auth-state">复用登录态</FieldLabel>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <button
                              aria-label="复用登录态说明"
                              className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground"
                              type="button"
                            >
                              <CircleHelp className="size-3.5" />
                            </button>
                          </TooltipTrigger>
                          <TooltipContent side="top">人工登录必须开启复用登录态。</TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </div>
                    <Select
                      id="environment-reuse-auth-state"
                      placeholder="选择复用策略"
                      setValue={setReuseAuthStateValue}
                      value={form.reuseAuthState ? "enabled" : "disabled"}
                    >
                      {reuseAuthStateOptions.map((value) => (
                        <SelectOption key={value} value={value}>
                          {reuseAuthStateLabels[value]}
                        </SelectOption>
                      ))}
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="environment-captcha-strategy">验证码策略</FieldLabel>
                    <Select
                      id="environment-captcha-strategy"
                      placeholder="选择验证码策略"
                      setValue={setCaptchaStrategyValue}
                      value={form.captchaStrategy}
                    >
                      {availableCaptchaStrategyOptions.map((value) => (
                        <SelectOption key={value} value={value}>
                          {captchaStrategyLabels[value]}
                        </SelectOption>
                      ))}
                    </Select>
                  </Field>
                </div>
                <Field className="sm:col-span-2">
                  <div className="font-medium text-sm">登录态信息</div>
                  <div
                    className={`relative grid overflow-hidden rounded-md border bg-muted/20 py-3 pr-3 pl-4 before:absolute before:inset-y-0 before:left-0 before:w-0.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-5 ${authStateAccentClassName}`}
                  >
                    <div className="min-w-0 space-y-1">
                      <div className="font-medium text-sm">{authStateSummaryLabel}</div>
                      {showManualAuthControls ? (
                        <div className="space-y-1 text-xs">
                          <p className="text-muted-foreground">
                            {manualAuthSession
                              ? manualAuthSession.message
                              : "登录成功后会自动保存并关闭窗口；如未自动关闭，可手动保存。"}
                          </p>
                          {!editingEnvironment?.has_saved_credentials ? (
                            <p className="text-amber-700 dark:text-amber-300">
                              当前环境未保存可自动填充的密码，登录窗口会打开但不会自动输入账号密码。
                            </p>
                          ) : null}
                        </div>
                      ) : showAiLetterAutoAuthStatus ? (
                        <p className="text-muted-foreground text-xs">
                          {selectedAuthStateStatus === "logging_in"
                            ? editingEnvironment?.auth_state_message ||
                              "正在通过 Playwright 自动登录（验证码 AI 识别，最多 3 次）…"
                            : selectedAuthStateStatus === "login_failed"
                              ? editingEnvironment?.auth_state_message ||
                                "自动登录失败，请检查账号密码或模型配置后重新保存环境。"
                              : selectedAuthStateStatus === "valid"
                                ? "登录态已自动保存，探索任务将直接复用。"
                                : "保存环境后将自动登录并保存登录态。"}
                        </p>
                      ) : selectedManualCaptcha && form.reuseAuthState ? (
                        <p className="text-muted-foreground text-xs">保存环境后可打开登录窗口并保存登录态。</p>
                      ) : (
                        <p className="text-muted-foreground text-xs">仅人工登录策略需要手动保存登录态。</p>
                      )}
                    </div>
                    <div className="mt-3 flex shrink-0 flex-wrap items-center gap-3 sm:mt-0 sm:flex-nowrap sm:justify-end">
                      {selectedAuthStateStatus === "valid" || selectedAuthStateStatus === "expired" ? (
                        <div className="min-w-32 sm:text-right">
                          <div className="font-medium text-xs">
                            {formatAuthStateTimeRemaining(selectedAuthStateExpiresAt)}
                          </div>
                          <div className="mt-0.5 whitespace-nowrap text-[11px] text-muted-foreground tabular-nums">
                            有效期至 {formatAuthStateExpiresAt(selectedAuthStateExpiresAt)}
                          </div>
                        </div>
                      ) : null}
                      {showManualAuthControls ? (
                        <div className="flex shrink-0 flex-wrap gap-2 lg:flex-nowrap lg:justify-end">
                          <Button
                            className="whitespace-nowrap"
                            disabled={manualAuthAction === "start"}
                            onClick={startManualAuth}
                            type="button"
                            variant="outline"
                          >
                            <LogIn className="size-4" />
                            打开登录
                          </Button>
                          {manualAuthSession ? (
                            <>
                              <Button
                                className="whitespace-nowrap"
                                disabled={manualAuthAction === "save"}
                                onClick={saveManualAuth}
                                type="button"
                                variant="outline"
                              >
                                <Save className="size-4" />
                                保存登录态
                              </Button>
                              <Button
                                className="whitespace-nowrap"
                                disabled={manualAuthAction === "cancel"}
                                onClick={() => void cancelManualAuth()}
                                type="button"
                                variant="ghost"
                              >
                                <X className="size-4" />
                                取消
                              </Button>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </Field>
              </>
            ) : null}
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="environment-description">描述</FieldLabel>
              <Textarea
                className="min-h-20"
                id="environment-description"
                onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                placeholder="例如：主站账号、回归专用账号、演示账号"
                value={form.description}
              />
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
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
            <DialogDescription>停止后将终止当前浏览器探索进程，已生成的日志和页面事实会保留。</DialogDescription>
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
    </PageShell>
  );
}
