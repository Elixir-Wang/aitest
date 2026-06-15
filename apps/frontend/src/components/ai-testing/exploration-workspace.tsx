"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSearchParams } from "next/navigation";

import { CircleHelp, Eye, EyeOff, LogIn, Pencil, Play, Plus, Save, Square, Trash2, X } from "lucide-react";
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
import { Loader } from "@/components/ui/loader";
import { authStateStatusTone, explorationStatusTone, StatusBadge } from "@/components/ui/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { type ApiProject, ApiRequestError, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type ProjectScope = "all" | "project";

type ProjectEnvironment = {
  id: string;
  project_id: string;
  project_name: string;
  name: string;
  site_url: string;
  username: string;
  login_strategy: string;
  captcha_strategy: string;
  reuse_auth_state: boolean;
  has_saved_credentials: boolean;
  auth_state_status: string;
  auth_state_expires_at: string | null;
  description: string;
  created_at: string;
  updated_at: string;
  available_actions: string[];
};

type RequirementDocument = {
  id: string;
  name: string;
  status: string;
  created_at: string;
};

type ExplorationRun = {
  id: string;
  project_id: string;
  project_name: string;
  environment_id: string;
  environment_name: string;
  requirement_doc_id: string;
  requirement_doc_title: string;
  title: string;
  status: string;
  scope: string;
  forbidden_paths: string;
  login_strategy: string;
  goal: string;
  notes: string;
  max_pages: number;
  max_actions: number;
  timeout_minutes: number;
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
  captchaStrategy: string;
  reuseAuthState: boolean;
  description: string;
};

type ManualAuthSession = {
  session_id: string;
  status: string;
  auth_state_status: string;
  auth_state_expires_at: string | null;
  has_saved_credentials: boolean;
  message: string;
};

type ExplorationForm = {
  title: string;
  projectId: string;
  environmentId: string;
  requirementDocId: string;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};

const emptyForm: EnvironmentForm = {
  name: "",
  projectId: "",
  siteUrl: "",
  username: "",
  password: "",
  loginStrategy: "skip_login",
  captchaStrategy: "none",
  reuseAuthState: true,
  description: "",
};

const emptyExplorationForm: ExplorationForm = {
  title: "",
  projectId: "",
  environmentId: "",
  requirementDocId: "",
  scope: "",
  forbiddenPaths: "",
  goal: "",
  notes: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};

const statusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  stopping: "正在停止",
  cancelled: "已停止",
  partial: "部分完成",
  completed: "已完成",
  blocked: "阻塞",
};

const loginStrategyLabels: Record<string, string> = {
  account_password: "账号密码",
  skip_login: "无需登录",
};

const captchaStrategyLabels: Record<string, string> = {
  none: "无",
  ai_letter: "字母 AI 校验",
  manual: "人工登录",
};

const reuseAuthStateLabels: Record<string, string> = {
  enabled: "开启",
  disabled: "关闭",
};

const authStateStatusLabels: Record<string, string> = {
  none: "无",
  valid: "有效",
  expired: "过期",
  unknown: "未检测",
};

function formatAuthStateExpiresAt(expiresAt: string | null | undefined) {
  return expiresAt ? formatDateTime(expiresAt) : "有效期未知";
}

const environmentLoginStrategyOptions = ["skip_login", "account_password"];
const captchaStrategyOptions = ["none", "ai_letter", "manual"];
const reuseAuthStateOptions = ["enabled", "disabled"];

const explorationTabs = ["探索列表", "探索环境"];
const NO_REQUIREMENT_VALUE = "__none__";
const STOPPABLE_EXPLORATION_STATUSES = new Set(["queued", "running"]);
const LOADING_EXPLORATION_STATUSES = new Set(["queued", "running", "stopping"]);
const ACTIVE_MANUAL_AUTH_SESSION_STATUSES = new Set(["waiting_human"]);
const explorationPlaceholders = {
  scope: "填写本次要探索的页面范围，例如全站、指定菜单、指定 URL 或核心模块。",
  forbiddenPaths: "填写禁止进入或点击的路径/动作，例如删除、支付、外发、批量通知、退出登录。",
  goal: "填写本次探索要验证的目标，例如遍历元素和链接，检查 401/403、登录跳转和异常页。",
};

function formFromEnvironment(environment: ProjectEnvironment): EnvironmentForm {
  return {
    name: environment.name,
    projectId: environment.project_id,
    siteUrl: environment.site_url,
    username: environment.username,
    password: "",
    loginStrategy: environment.login_strategy,
    captchaStrategy: environment.captcha_strategy ?? "none",
    reuseAuthState: environment.reuse_auth_state ?? true,
    description: environment.description,
  };
}

function isManualAuthEnabled(environment: ProjectEnvironment | null) {
  return Boolean(
    environment &&
      environment.login_strategy === "account_password" &&
      environment.captcha_strategy === "manual" &&
      environment.reuse_auth_state,
  );
}

function formMatchesSavedManualAuthConfig(environment: ProjectEnvironment | null, form: EnvironmentForm) {
  return Boolean(
    environment &&
      form.loginStrategy === environment.login_strategy &&
      form.captchaStrategy === environment.captcha_strategy &&
      form.reuseAuthState === environment.reuse_auth_state &&
      form.siteUrl === environment.site_url &&
      form.username === environment.username &&
      form.password.length === 0,
  );
}

function isActiveManualAuthSession(session: ManualAuthSession | null) {
  return Boolean(session && ACTIVE_MANUAL_AUTH_SESSION_STATUSES.has(session.status));
}

function ExplorationStatusBadge({ status }: { status: string }) {
  const isLoading = LOADING_EXPLORATION_STATUSES.has(status);

  return (
    <StatusBadge tone={explorationStatusTone(status)}>
      {isLoading ? <Loader className="-ml-0.5" size={12} /> : null}
      {statusLabels[status] ?? status}
    </StatusBadge>
  );
}

function isManualAuthSessionEnded(session: ManualAuthSession) {
  return ["ended", "cancelled", "saved", "auto_saved"].includes(session.status);
}

function isMissingManualAuthSessionError(error: unknown) {
  return error instanceof ApiRequestError && error.code === "MANUAL_AUTH_SESSION_NOT_FOUND";
}

function parsePositiveInteger(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

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
  const [manualAuthSession, setManualAuthSession] = useState<ManualAuthSession | null>(null);
  const [manualAuthAction, setManualAuthAction] = useState<"cancel" | "save" | "start" | "">("");
  const [stoppingExploration, setStoppingExploration] = useState<ExplorationRun | null>(null);
  const [stoppingExplorationId, setStoppingExplorationId] = useState("");
  const [explorationLoading, setExplorationLoading] = useState(true);
  const [environmentLoading, setEnvironmentLoading] = useState(true);
  const [requirementLoading, setRequirementLoading] = useState(false);
  const [projectLoading, setProjectLoading] = useState(projectScope === "all");
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [projects, setProjects] = useState<ApiProject[]>([]);
  const [requirements, setRequirements] = useState<RequirementDocument[]>([]);
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
  const selectedProjectId = projectScope === "project" ? (projectId ?? "") : explorationForm.projectId;

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

  useEffect(() => {
    let ignore = false;
    const targetProjectId = selectedProjectId;
    if (!targetProjectId) {
      setRequirements([]);
      setRequirementLoading(false);
      return;
    }

    async function loadRequirements() {
      setRequirementLoading(true);
      try {
        const data = await apiRequest<RequirementDocument[]>(`/projects/${targetProjectId}/requirements`);
        if (!ignore) {
          setRequirements(data);
          setExplorationForm((current) => ({
            ...current,
            requirementDocId: data.some((item) => item.id === current.requirementDocId) ? current.requirementDocId : "",
          }));
        }
      } catch (requestError) {
        if (!ignore) {
          setRequirements([]);
          reportError(requestError, {
            fallbackMessage: "需求列表加载失败",
            actionLabel: "加载需求",
            method: "GET",
            path: `/projects/${targetProjectId}/requirements`,
          });
        }
      } finally {
        if (!ignore) {
          setRequirementLoading(false);
        }
      }
    }

    void loadRequirements();

    return () => {
      ignore = true;
    };
  }, [selectedProjectId]);

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
        ].some((value) => value.toLowerCase().includes(searchText.trim().toLowerCase())),
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
          statusLabels[item.status] ?? item.status,
          item.scope,
          item.goal,
          item.notes,
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
  const hasReusableEnvironmentPassword =
    editingEnvironment?.login_strategy === "account_password" && editingEnvironment.has_saved_credentials;
  const canCreateEnvironment =
    form.name.trim().length > 0 &&
    form.siteUrl.trim().length > 0 &&
    (projectScope === "project" || form.projectId.length > 0) &&
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
  const savedManualAuthEnabled = isManualAuthEnabled(editingEnvironment);
  const showManualAuthControls =
    savedManualAuthEnabled && selectedManualCaptcha && formMatchesSavedManualAuthConfig(editingEnvironment, form);
  const manualAuthSessionActive = isActiveManualAuthSession(manualAuthSession);
  const availableEnvironments = rows.filter((environment) => environment.project_id === selectedProjectId);
  const availableRequirements = useMemo(
    () => requirements.filter((requirement) => requirement.status !== "archived"),
    [requirements],
  );
  const selectedRequirementLabel = useMemo(() => {
    const selected = availableRequirements.find((item) => item.id === explorationForm.requirementDocId);
    return selected?.name ?? "";
  }, [availableRequirements, explorationForm.requirementDocId]);
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
    const statusPath = `/projects/${editingEnvironment.project_id}/environments/${environmentId}/manual-auth/${manualAuthSession.session_id}/status`;

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
      setForm({ ...emptyForm, projectId: projectId ?? form.projectId });
    }
  }

  function openEditExplorationDialog(run: ExplorationRun) {
    setEditingExploration(run);
    setExplorationForm({
      title: run.title,
      projectId: run.project_id,
      environmentId: run.environment_id,
      requirementDocId: run.requirement_doc_id,
      scope: run.scope,
      forbiddenPaths: run.forbidden_paths,
      goal: run.goal,
      notes: run.notes,
      maxPages: String(run.max_pages ?? 50),
      maxActions: String(run.max_actions ?? 1000),
      timeoutMinutes: String(run.timeout_minutes ?? 120),
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

        const updated = await apiRequest<ProjectEnvironment>(
          `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}`,
          {
            method: "PATCH",
            body: JSON.stringify(payload),
          },
        );
        setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)));
        setEditingEnvironment(updated);
        setForm(formFromEnvironment(updated));
        if (isManualAuthEnabled(updated)) {
          setManualAuthSession(null);
          toast.success("环境已更新，可打开登录窗口保存登录态");
          return;
        }
        toast.success("环境已更新");
      } else {
        // 创建环境
        const created = await apiRequest<ProjectEnvironment>(`/projects/${targetProjectId}/environments`, {
          method: "POST",
          body: JSON.stringify({
            project_id: targetProjectId,
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
        toast.success("环境已创建");
      }
      handleEnvironmentDialogOpenChange(false);
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: editingEnvironment ? "环境更新失败" : "环境创建失败",
        actionLabel: editingEnvironment ? "更新环境" : "创建环境",
        method: editingEnvironment ? "PATCH" : "POST",
        path: editingEnvironment
          ? `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}`
          : `/projects/${targetProjectId}/environments`,
      });
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
    const maxPages = parsePositiveInteger(explorationForm.maxPages);
    const maxActions = parsePositiveInteger(explorationForm.maxActions);
    const timeoutMinutes = parsePositiveInteger(explorationForm.timeoutMinutes);
    if (!maxPages || !maxActions || !timeoutMinutes) {
      toast.error("请填写大于 0 的执行边界");
      return;
    }

    try {
      const payload = {
        environment_id: explorationForm.environmentId,
        requirement_doc_id: explorationForm.requirementDocId,
        title: explorationForm.title,
        scope: explorationForm.scope,
        forbidden_paths: explorationForm.forbiddenPaths,
        goal: explorationForm.goal,
        notes: explorationForm.notes,
        max_pages: maxPages,
        max_actions: maxActions,
        timeout_minutes: timeoutMinutes,
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
      reportError(requestError, {
        fallbackMessage: editingExploration ? "探索任务更新失败" : "探索任务创建失败",
        actionLabel: editingExploration ? "更新探索任务" : "创建探索任务",
        method: editingExploration ? "PATCH" : "POST",
        path: editingExploration
          ? `/projects/${editingExploration.project_id}/exploration-runs/${editingExploration.id}`
          : `/projects/${targetProjectId}/exploration-runs`,
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
          return apiRequest(`/projects/${run.project_id}/exploration-runs/${id}`, { method: "DELETE" });
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
      const updated = await apiRequest<ExplorationRun>(`/projects/${run.project_id}/exploration-runs/${run.id}/stop`, {
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
        path: `/projects/${run.project_id}/exploration-runs/${run.id}/stop`,
      });
    } finally {
      setStoppingExplorationId("");
    }
  }

  async function startManualAuth() {
    if (!editingEnvironment) {
      return;
    }
    setManualAuthAction("start");
    try {
      const session = await apiRequest<ManualAuthSession>(
        `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/start`,
        { method: "POST" },
      );
      setManualAuthSession(session);
      toast.success(session.message || "登录窗口已打开");
    } catch (requestError) {
      reportError(requestError, {
        fallbackMessage: "打开人工登录窗口失败",
        actionLabel: "打开人工登录窗口",
        method: "POST",
        path: `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/start`,
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
        `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/save`,
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
        path: `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/save`,
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
        `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/cancel`,
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
          path: `/projects/${editingEnvironment.project_id}/environments/${editingEnvironment.id}/manual-auth/${manualAuthSession.session_id}/cancel`,
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
          return apiRequest(`/projects/${environment.project_id}/environments/${id}`, { method: "DELETE" });
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
        path: "/projects/{projectId}/environments/{environmentId}",
      });
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
                  <TableHead>关联需求</TableHead>
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
                    <TableCell>{item.requirement_doc_title || "-"}</TableCell>
                    <TableCell>
                      <ExplorationStatusBadge status={item.status} />
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
                  <TableLoadingRow colSpan={9} label="探索任务加载中" />
                ) : null}
                {!explorationLoading && filteredExplorationRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={9}>
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
            placeholder="搜索环境名称、项目、站点或用户名"
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
                  <TableHead>登录态</TableHead>
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
                      <div className="flex min-w-28">
                        <StatusBadge tone={authStateStatusTone(item.auth_state_status)}>
                          {authStateStatusLabels[item.auth_state_status] ?? item.auth_state_status}
                        </StatusBadge>
                      </div>
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
                  <TableLoadingRow colSpan={6} label="环境列表加载中" />
                ) : null}
                {!environmentLoading && filteredRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={6}>
                      暂无环境。新增站点环境后，可用于后续页面探索任务。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      ) : null}

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
              <FieldLabel htmlFor="environment-project">项目 *</FieldLabel>
              <Select
                aria-required="true"
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
                  <div className="grid gap-3 rounded-md border bg-muted/20 px-3 py-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground text-xs">登录态</span>
                        <StatusBadge tone={authStateStatusTone(selectedAuthStateStatus)}>
                          {authStateStatusLabels[selectedAuthStateStatus] ?? selectedAuthStateStatus}
                        </StatusBadge>
                      </div>
                      {selectedAuthStateStatus === "valid" || selectedAuthStateStatus === "expired" ? (
                        <p className="text-muted-foreground text-xs">
                          有效期：{formatAuthStateExpiresAt(selectedAuthStateExpiresAt)}
                        </p>
                      ) : null}
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
                      ) : selectedManualCaptcha && form.reuseAuthState ? (
                        <p className="text-muted-foreground text-xs">保存环境后可打开登录窗口并保存登录态。</p>
                      ) : (
                        <p className="text-muted-foreground text-xs">仅人工登录策略需要手动保存登录态。</p>
                      )}
                    </div>
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
        <DialogContent className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="shrink-0 gap-3 px-6 pt-6">
            <DialogTitle>{editingExploration ? "编辑探索任务" : "新建探索任务"}</DialogTitle>
            <DialogDescription>选择环境并配置探索范围、探索目标和禁止路径。</DialogDescription>
          </DialogHeader>
          <FieldGroup className="grid min-h-0 gap-x-6 gap-y-5 overflow-y-auto px-6 py-5 sm:grid-cols-2">
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
                    requirementDocId: "",
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
            <Field>
              <FieldLabel htmlFor="exploration-requirement">需求</FieldLabel>
              <Select
                id="exploration-requirement"
                placeholder={requirementLoading ? "加载需求中..." : "选择需求或留空"}
                setValue={(value) =>
                  setExplorationForm((current) => ({
                    ...current,
                    requirementDocId: value === NO_REQUIREMENT_VALUE ? "" : value,
                  }))
                }
                value={explorationForm.requirementDocId || NO_REQUIREMENT_VALUE}
              >
                <SelectOption value={NO_REQUIREMENT_VALUE}>不关联需求</SelectOption>
                {availableRequirements.map((requirement) => (
                  <SelectOption key={requirement.id} value={requirement.id}>
                    {requirement.name}
                  </SelectOption>
                ))}
              </Select>
              {selectedRequirementLabel ? (
                <p className="text-muted-foreground text-xs">已关联：{selectedRequirementLabel}</p>
              ) : null}
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-scope">探索范围</FieldLabel>
              <Textarea
                className="min-h-24"
                id="exploration-scope"
                onChange={(event) => setExplorationForm((current) => ({ ...current, scope: event.target.value }))}
                placeholder={explorationPlaceholders.scope}
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
                placeholder={explorationPlaceholders.forbiddenPaths}
                value={explorationForm.forbiddenPaths}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-goal">探索目标</FieldLabel>
              <Textarea
                className="min-h-20"
                id="exploration-goal"
                onChange={(event) => setExplorationForm((current) => ({ ...current, goal: event.target.value }))}
                placeholder={explorationPlaceholders.goal}
                value={explorationForm.goal}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel htmlFor="exploration-notes">备注</FieldLabel>
              <Textarea
                className="min-h-16"
                id="exploration-notes"
                onChange={(event) => setExplorationForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="补充说明，不参与探索目标判定"
                value={explorationForm.notes}
              />
            </Field>
            <Field className="sm:col-span-2">
              <FieldLabel>执行边界</FieldLabel>
              <div className="grid gap-3 sm:grid-cols-3">
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-max-pages">
                  <span className="text-muted-foreground text-xs">页面上限</span>
                  <Input
                    id="exploration-max-pages"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxPages: event.target.value }))
                    }
                    placeholder="50"
                    type="number"
                    value={explorationForm.maxPages}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-max-actions">
                  <span className="text-muted-foreground text-xs">操作上限</span>
                  <Input
                    id="exploration-max-actions"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, maxActions: event.target.value }))
                    }
                    placeholder="1000"
                    type="number"
                    value={explorationForm.maxActions}
                  />
                </label>
                <label className="grid gap-1.5 text-sm" htmlFor="exploration-timeout-minutes">
                  <span className="text-muted-foreground text-xs">超时时间（分钟）</span>
                  <Input
                    id="exploration-timeout-minutes"
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setExplorationForm((current) => ({ ...current, timeoutMinutes: event.target.value }))
                    }
                    placeholder="120"
                    type="number"
                    value={explorationForm.timeoutMinutes}
                  />
                </label>
              </div>
            </Field>
          </FieldGroup>
          <DialogFooter className="m-0 shrink-0 px-6 py-4">
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
