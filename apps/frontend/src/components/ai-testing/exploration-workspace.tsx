"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useRouter, useSearchParams } from "next/navigation";

import {
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Eye,
  EyeOff,
  FileCode2,
  FileText,
  Folder,
  FolderOpen,
  LogIn,
  Pencil,
  Play,
  Plus,
  Save,
  Square,
  Trash2,
  X,
} from "lucide-react";
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
import { notifyAiTaskStarted } from "@/lib/ai-task-events";
import { type ApiProject, ApiRequestError, apiRequest, formatDateTime } from "@/lib/api-client";
import { reportError } from "@/lib/error-feedback";

type ProjectScope = "all" | "project";
type ExplorationMode = "goal" | "autonomous";

type ExplorationEnvironment = {
  id: string;
  name: string;
  site_url: string;
  username: string;
  login_strategy: string;
  captcha_strategy: string;
  reuse_auth_state: boolean;
  has_saved_credentials: boolean;
  auth_state_status: string;
  auth_state_expires_at: string | null;
  auth_state_message?: string;
  auto_auth_status?: string;
  auto_auth_message?: string;
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
  requirement_doc_id: string;
  requirement_doc_title: string;
  title: string;
  status: string;
  exploration_mode: ExplorationMode;
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

type ProjectArtifactRow = {
  project_id: string;
  project_name: string;
};

type ExplorationPageRecord = {
  id: string;
  exploration_run_id: string;
  module_key: string;
  title: string;
  url: string;
  entry_path: string;
  structure_summary: string;
  snapshot_path: string;
  trace_path: string;
  created_at: string;
  updated_at: string;
};

type ExplorationPageYamlContent = {
  page_id: string;
  file_name: string;
  file_path: string;
  content: string;
};

type ExplorationPageTreeNode = {
  id: string;
  name: string;
  path: string;
  type: "folder" | "page";
  children: ExplorationPageTreeNode[];
  page?: ExplorationPageRecord;
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

const emptyForm: EnvironmentForm = {
  name: "",
  siteUrl: "",
  username: "",
  password: "",
  loginStrategy: "skip_login",
  captchaStrategy: "none",
  reuseAuthState: true,
  description: "",
};

const statusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  stopping: "正在停止",
  cancelled: "已停止",
  interrupted: "已中断",
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
  logging_in: "登录中",
  login_failed: "登录失败",
};

const LOGGING_IN_AUTH_STATE_STATUSES = new Set(["logging_in"]);

function formatAuthStateExpiresAt(expiresAt: string | null | undefined) {
  return expiresAt ? formatDateTime(expiresAt) : "有效期未知";
}

const environmentLoginStrategyOptions = ["skip_login", "account_password"];
const captchaStrategyOptions = ["none", "ai_letter", "manual"];
const reuseAuthStateOptions = ["enabled", "disabled"];

const explorationTabs = ["探索列表", "探索环境", "探索产物"];
const STOPPABLE_EXPLORATION_STATUSES = new Set(["queued", "running"]);
const LOADING_EXPLORATION_STATUSES = new Set(["queued", "running", "stopping"]);
const ACTIVE_MANUAL_AUTH_SESSION_STATUSES = new Set(["waiting_human"]);

function formFromEnvironment(environment: ExplorationEnvironment): EnvironmentForm {
  return {
    name: environment.name,
    siteUrl: environment.site_url,
    username: environment.username,
    password: "",
    loginStrategy: environment.login_strategy,
    captchaStrategy: environment.captcha_strategy ?? "none",
    reuseAuthState: environment.reuse_auth_state ?? true,
    description: environment.description,
  };
}

function isManualAuthEnabled(environment: ExplorationEnvironment | null) {
  return Boolean(
    environment &&
      environment.login_strategy === "account_password" &&
      environment.captcha_strategy === "manual" &&
      environment.reuse_auth_state,
  );
}

function isAiLetterAutoAuthEnabled(environment: ExplorationEnvironment | null) {
  return Boolean(
    environment &&
      environment.login_strategy === "account_password" &&
      environment.captcha_strategy === "ai_letter" &&
      environment.reuse_auth_state,
  );
}

function canStartAiLetterAutoAuth(environment: ExplorationEnvironment) {
  return isAiLetterAutoAuthEnabled(environment) && environment.has_saved_credentials;
}

function formMatchesSavedManualAuthConfig(environment: ExplorationEnvironment | null, form: EnvironmentForm) {
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

function EnvironmentAuthStateBadge({ message, status }: { message?: string; status: string }) {
  const isLoading = LOGGING_IN_AUTH_STATE_STATUSES.has(status);
  const badge = (
    <StatusBadge tone={authStateStatusTone(status)}>
      {isLoading ? <Loader className="-ml-0.5" size={12} /> : null}
      {authStateStatusLabels[status] ?? status}
    </StatusBadge>
  );

  if (!message) {
    return badge;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex">{badge}</span>
        </TooltipTrigger>
        <TooltipContent side="top">{message}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function isManualAuthSessionEnded(session: ManualAuthSession) {
  return ["ended", "cancelled", "saved", "auto_saved"].includes(session.status);
}

function isMissingManualAuthSessionError(error: unknown) {
  return error instanceof ApiRequestError && error.code === "MANUAL_AUTH_SESSION_NOT_FOUND";
}

function pageDisplayPath(page: ExplorationPageRecord) {
  return (
    page.entry_path ||
    (() => {
      try {
        return new URL(page.url).pathname || "/";
      } catch {
        return page.url || "/";
      }
    })()
  );
}

function buildPageTree(pages: ExplorationPageRecord[]): ExplorationPageTreeNode {
  const root: ExplorationPageTreeNode = {
    id: "root",
    name: "页面",
    path: "/",
    type: "folder",
    children: [],
  };

  for (const page of pages) {
    const path = pageDisplayPath(page);
    const segments = path.split("/").filter(Boolean);
    const nodeSegments = segments.length > 0 ? segments : ["首页"];
    let current = root;
    let currentPath = "";

    nodeSegments.forEach((segment, index) => {
      currentPath = segment === "首页" && path === "/" ? "/" : `${currentPath}/${segment}`;
      const isPage = index === nodeSegments.length - 1;
      const nodeId = isPage ? page.id : `folder:${currentPath}`;
      let child = current.children.find((item) => item.id === nodeId);
      if (!child) {
        child = {
          id: nodeId,
          name: isPage ? page.title || segment : segment,
          path: isPage ? path : currentPath,
          type: isPage ? "page" : "folder",
          children: [],
          page: isPage ? page : undefined,
        };
        current.children.push(child);
      }
      if (isPage) {
        child.page = page;
        child.name = page.title || child.name;
      }
      current = child;
    });
  }

  return root;
}

function collectPageFolderIds(node: ExplorationPageTreeNode): string[] {
  return node.children.flatMap((child) => [
    ...(child.type === "folder" ? [child.id] : []),
    ...collectPageFolderIds(child),
  ]);
}

function findPageNode(node: ExplorationPageTreeNode, pageId: string): ExplorationPageTreeNode | null {
  if (node.id === pageId) {
    return node;
  }
  for (const child of node.children) {
    const found = findPageNode(child, pageId);
    if (found) {
      return found;
    }
  }
  return null;
}

function ExplorationProjectPagesTree({
  expandedNodeIds,
  loading,
  onPageSelect,
  onToggleNode,
  pages,
  projectId,
  selectedPageId,
}: {
  expandedNodeIds: string[];
  loading: boolean;
  onPageSelect: (pageId: string) => void;
  onToggleNode: (nodeId: string) => void;
  pages: ExplorationPageRecord[];
  projectId: string;
  selectedPageId: string;
}) {
  const tree = useMemo(() => buildPageTree(pages), [pages]);
  const selectedNode = selectedPageId ? findPageNode(tree, selectedPageId) : null;
  const selectedPage = selectedNode?.page ?? pages[0] ?? null;
  const effectiveExpandedIds = expandedNodeIds.length > 0 ? expandedNodeIds : collectPageFolderIds(tree);
  const [yamlContent, setYamlContent] = useState<ExplorationPageYamlContent | null>(null);
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlError, setYamlError] = useState("");

  useEffect(() => {
    if (!selectedPageId && pages[0]) {
      onPageSelect(pages[0].id);
    }
  }, [onPageSelect, pages, selectedPageId]);

  useEffect(() => {
    if (!selectedPage?.id || !projectId) {
      setYamlContent(null);
      setYamlError("");
      return;
    }

    let ignore = false;
    setYamlLoading(true);
    setYamlError("");

    async function loadYamlContent() {
      try {
        const data = await apiRequest<ExplorationPageYamlContent>(
          `/page-exploration/projects/${projectId}/pages/${selectedPage.id}/yaml`,
        );
        if (!ignore) {
          setYamlContent(data);
        }
      } catch (requestError) {
        if (!ignore) {
          setYamlContent(null);
          setYamlError(requestError instanceof Error ? requestError.message : "YAML 文件加载失败");
        }
      } finally {
        if (!ignore) {
          setYamlLoading(false);
        }
      }
    }

    void loadYamlContent();

    return () => {
      ignore = true;
    };
  }, [projectId, selectedPage?.id]);

  return (
    <div className="overflow-hidden rounded-lg border bg-background">
      {loading ? (
        <div className="p-6">
          <Table>
            <TableBody>
              <TableLoadingRow colSpan={1} label="页面信息加载中" />
            </TableBody>
          </Table>
        </div>
      ) : pages.length === 0 ? (
        <div className="p-8 text-center text-muted-foreground text-sm">暂无页面信息。</div>
      ) : (
        <div className="grid min-h-[30rem] lg:grid-cols-[18rem_minmax(0,1fr)]">
          <aside className="min-h-0 border-b bg-muted/20 lg:border-r lg:border-b-0">
            <div className="border-b px-3 py-2 font-medium text-sm">页面目录</div>
            <div className="max-h-[34rem] overflow-auto p-2">
              {tree.children.map((node) => (
                <ExplorationPageTreeItem
                  activePageId={selectedPage?.id ?? ""}
                  depth={0}
                  expandedNodeIds={effectiveExpandedIds}
                  key={node.id}
                  node={node}
                  onPageSelect={onPageSelect}
                  onToggleNode={onToggleNode}
                />
              ))}
            </div>
          </aside>
          <main className="min-w-0 p-4">
            {selectedPage ? (
              <YamlCodePreview content={yamlContent?.content ?? ""} error={yamlError} loading={yamlLoading} />
            ) : null}
          </main>
        </div>
      )}
    </div>
  );
}

function ExplorationPageTreeItem({
  activePageId,
  depth,
  expandedNodeIds,
  node,
  onPageSelect,
  onToggleNode,
}: {
  activePageId: string;
  depth: number;
  expandedNodeIds: string[];
  node: ExplorationPageTreeNode;
  onPageSelect: (pageId: string) => void;
  onToggleNode: (nodeId: string) => void;
}) {
  const isFolder = node.type === "folder";
  const expanded = isFolder && expandedNodeIds.includes(node.id);
  const active = node.type === "page" && node.id === activePageId;

  return (
    <div>
      <div
        className={
          active
            ? "flex h-8 items-center gap-1 rounded-md bg-primary/10 px-1 text-primary"
            : "flex h-8 items-center gap-1 rounded-md px-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        }
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
      >
        {isFolder ? (
          <button
            aria-label={expanded ? "收起页面分组" : "展开页面分组"}
            className="flex size-5 items-center justify-center rounded-sm hover:bg-background"
            onClick={() => onToggleNode(node.id)}
            type="button"
          >
            {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          </button>
        ) : (
          <span className="size-5" />
        )}
        <button
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm"
          onClick={() => {
            if (isFolder) {
              onToggleNode(node.id);
            } else {
              onPageSelect(node.id);
            }
          }}
          type="button"
        >
          {isFolder ? (
            expanded ? (
              <FolderOpen className="size-4 shrink-0" />
            ) : (
              <Folder className="size-4 shrink-0" />
            )
          ) : (
            <FileText className="size-4 shrink-0" />
          )}
          <span className="truncate">{node.name}</span>
        </button>
      </div>
      {isFolder && expanded
        ? node.children.map((child) => (
            <ExplorationPageTreeItem
              activePageId={activePageId}
              depth={depth + 1}
              expandedNodeIds={expandedNodeIds}
              key={child.id}
              node={child}
              onPageSelect={onPageSelect}
              onToggleNode={onToggleNode}
            />
          ))
        : null}
    </div>
  );
}

function renderYamlValue(value: string): ReactNode {
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (trimmed.startsWith("#")) return <span className="text-slate-400">{value}</span>;
  if (/^["'].*["']$/.test(trimmed)) {
    return <span className="text-emerald-700 dark:text-emerald-300">{value}</span>;
  }
  if (/^(true|false|null)$/i.test(trimmed)) {
    return <span className="font-medium text-violet-700 dark:text-violet-300">{value}</span>;
  }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return <span className="font-medium text-blue-700 dark:text-blue-300">{value}</span>;
  }
  return <span className="text-slate-700 dark:text-slate-200">{value}</span>;
}

function renderYamlLine(line: string): ReactNode {
  if (!line.trim()) return <span>&nbsp;</span>;

  const commentIndex = line.indexOf("#");
  const content = commentIndex >= 0 ? line.slice(0, commentIndex) : line;
  const comment = commentIndex >= 0 ? line.slice(commentIndex) : "";
  const match = content.match(/^(\s*)(-\s*)?([^:#]+?)(\s*:\s*)(.*)$/);

  if (!match) {
    return (
      <>
        <span className="text-slate-700 dark:text-slate-200">{content}</span>
        {comment ? <span className="text-slate-400">{comment}</span> : null}
      </>
    );
  }

  const [, indent, dash = "", key, colon, value] = match;
  return (
    <>
      <span>{indent}</span>
      {dash ? <span className="text-amber-600 dark:text-amber-300">{dash}</span> : null}
      <span className="font-semibold text-cyan-800 dark:text-cyan-200">{key}</span>
      <span className="text-slate-400">{colon}</span>
      {renderYamlValue(value)}
      {comment ? <span className="text-slate-400">{comment}</span> : null}
    </>
  );
}

function YamlCodePreview({ content, error, loading }: { content: string; error: string; loading: boolean }) {
  if (loading) {
    return (
      <div className="grid min-h-72 place-items-center rounded-lg border border-dashed bg-slate-50 text-muted-foreground text-sm dark:bg-slate-950/40">
        <div className="flex items-center gap-2">
          <Loader className="size-4" />
          YAML 文件加载中
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/8 p-4 text-destructive text-sm">
        {error}
      </div>
    );
  }

  const lines = content
    ? content.split("\n").map((line, index) => ({
        id: `${index + 1}:${line}`,
        line,
        number: index + 1,
      }))
    : [];
  if (lines.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-muted-foreground text-sm">
        暂无 YAML 内容。
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border bg-slate-50 shadow-sm dark:bg-slate-950/60">
      <div className="flex h-9 items-center justify-between border-b bg-white/80 px-3 dark:bg-slate-900/70">
        <div className="flex items-center gap-2 font-medium text-slate-700 text-xs dark:text-slate-200">
          <FileCode2 className="size-3.5 text-cyan-700 dark:text-cyan-300" />
          YAML
        </div>
        <div className="text-slate-400 text-xs">{lines.length} 行</div>
      </div>
      <pre className="max-h-[34rem] overflow-auto p-0 font-mono text-[12px] leading-6">
        {lines.map((line) => (
          <div
            className="grid grid-cols-[3.5rem_minmax(0,1fr)] border-slate-200/55 border-b last:border-b-0 dark:border-slate-800/70"
            key={line.id}
          >
            <span className="select-none border-r bg-slate-100/70 px-3 text-right text-slate-400 dark:border-slate-800 dark:bg-slate-900/70">
              {line.number}
            </span>
            <code className="min-w-0 whitespace-pre-wrap break-words px-3 text-slate-700 dark:text-slate-200">
              {renderYamlLine(line.line)}
            </code>
          </div>
        ))}
      </pre>
    </div>
  );
}

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
  const [form, setForm] = useState<EnvironmentForm>({ ...emptyForm });
  const [selectedArtifactProjectId, setSelectedArtifactProjectId] = useState("");
  const [projectPages, setProjectPages] = useState<ExplorationPageRecord[]>([]);
  const [projectPagesLoading, setProjectPagesLoading] = useState(false);
  const [selectedPageId, setSelectedPageId] = useState("");
  const [expandedPageNodeIds, setExpandedPageNodeIds] = useState<string[]>([]);
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
        const data = await apiRequest<ExplorationEnvironment[]>("/environments");
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
  }, [setRows]);

  const hasLoggingInEnvironment = useMemo(() => rows.some((item) => item.auth_state_status === "logging_in"), [rows]);

  useEffect(() => {
    if (!hasLoggingInEnvironment) {
      return;
    }

    let ignore = false;
    const environmentsPath = "/environments";

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
  }, [hasLoggingInEnvironment, setRows]);

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
          statusLabels[item.status] ?? item.status,
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

  useEffect(() => {
    if (activeTab !== "探索产物" || !selectedArtifactProject) {
      return;
    }

    void loadProjectPages(selectedArtifactProject);
  }, [activeTab, loadProjectPages, selectedArtifactProject]);

  const hasReusableEnvironmentPassword =
    editingEnvironment?.login_strategy === "account_password" && editingEnvironment.has_saved_credentials;
  const canCreateEnvironment =
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
    setForm({ ...emptyForm });
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
      setForm({ ...emptyForm });
    }
  }

  function openEditExplorationDialog(run: ExplorationRun) {
    router.push(`/projects/${run.project_id}/exploration/${run.id}/edit`);
  }

  async function saveEnvironment() {
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
                          ...((item.available_actions ?? []).includes("start")
                            ? [
                                {
                                  label: item.status === "pending" ? "开始探索" : "重新探索",
                                  icon: Play,
                                  disabled: startingExplorationId === item.id,
                                  onSelect: () => void startExplorationRun(item),
                                },
                              ]
                            : []),
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
            placeholder="搜索环境名称、站点或用户名"
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
                    <TableCell>
                      <span className="block max-w-72 truncate" title={item.site_url}>
                        {item.site_url}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex min-w-28">
                        <EnvironmentAuthStateBadge message={item.auth_state_message} status={item.auth_state_status} />
                      </div>
                    </TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell>
                      <RowActions
                        actions={[
                          ...(canStartAiLetterAutoAuth(item)
                            ? [
                                {
                                  label: item.auth_state_status === "logging_in" ? "登录中" : "登录",
                                  icon: LogIn,
                                  disabled: item.auth_state_status === "logging_in",
                                  onSelect: () => void startAiLetterAutoAuth(item),
                                },
                              ]
                            : []),
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
                  <TableLoadingRow colSpan={5} label="环境列表加载中" />
                ) : null}
                {!environmentLoading && filteredRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="h-24 text-center text-muted-foreground" colSpan={5}>
                      暂无环境。新增站点环境后，可用于后续页面探索任务。
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>
        </ShellSection>
      ) : null}

      {activeTab === "探索产物" ? (
        <ShellSection>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-medium text-sm">项目列表</h2>
            <div className="flex items-center gap-3">
              <span className="font-medium text-muted-foreground text-sm">项目选择</span>
              <Select
                className="w-56"
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
            <div className="rounded-lg border p-8 text-center text-muted-foreground text-sm">暂无可切换项目。</div>
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
                  <div className="grid gap-3 rounded-md border bg-muted/20 px-3 py-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground text-xs">登录态</span>
                        <EnvironmentAuthStateBadge
                          message={editingEnvironment?.auth_state_message}
                          status={selectedAuthStateStatus}
                        />
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
