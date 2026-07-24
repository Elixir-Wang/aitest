import { Loader } from "@/components/ui/loader";
import { authStateStatusTone, explorationStatusTone, StatusBadge } from "@/components/ui/status-badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ApiRequestError, formatDateTime } from "@/lib/api-client";
import type { ExplorationEnvironment } from "@/lib/exploration-types";

export type EnvironmentForm = {
  projectId: string;
  name: string;
  siteUrl: string;
  username: string;
  password: string;
  loginStrategy: string;
  captchaStrategy: string;
  reuseAuthState: boolean;
  description: string;
};

export type ManualAuthSession = {
  session_id: string;
  status: string;
  auth_state_status: string;
  auth_state_expires_at: string | null;
  has_saved_credentials: boolean;
  message: string;
};

export const emptyEnvironmentForm: EnvironmentForm = {
  projectId: "",
  name: "",
  siteUrl: "",
  username: "",
  password: "",
  loginStrategy: "skip_login",
  captchaStrategy: "none",
  reuseAuthState: true,
  description: "",
};

export const explorationStatusLabels: Record<string, string> = {
  pending: "待执行",
  queued: "排队中",
  running: "探索中",
  stopping: "正在停止",
  cancelled: "已停止",
  interrupted: "已中断",
  completed: "已完成",
  blocked: "阻塞",
};

export const loginStrategyLabels: Record<string, string> = {
  account_password: "账号密码",
  skip_login: "无需登录",
};

export const captchaStrategyLabels: Record<string, string> = {
  none: "无",
  ai_letter: "字母 AI 校验",
  manual: "人工登录",
};

export const reuseAuthStateLabels: Record<string, string> = {
  enabled: "开启",
  disabled: "关闭",
};

export const authStateStatusLabels: Record<string, string> = {
  none: "无",
  valid: "有效",
  expired: "过期",
  unknown: "未检测",
  logging_in: "登录中",
  login_failed: "登录失败",
};

export const environmentLoginStrategyOptions = ["skip_login", "account_password"];
export const captchaStrategyOptions = ["none", "ai_letter", "manual"];
export const reuseAuthStateOptions = ["enabled", "disabled"];

const LOGGING_IN_AUTH_STATE_STATUSES = new Set(["logging_in"]);
const LOADING_EXPLORATION_STATUSES = new Set(["queued", "running", "stopping"]);
const ACTIVE_MANUAL_AUTH_SESSION_STATUSES = new Set(["waiting_human"]);

export function formatAuthStateExpiresAt(expiresAt: string | null | undefined) {
  return expiresAt ? formatDateTime(expiresAt) : "有效期未知";
}

export function formatAuthStateTimeRemaining(expiresAt: string | null | undefined, now = new Date()) {
  if (!expiresAt) return "有效期未知";

  const expiresAtTimestamp = new Date(expiresAt).getTime();
  if (Number.isNaN(expiresAtTimestamp)) return "有效期未知";

  const remainingMinutes = Math.ceil((expiresAtTimestamp - now.getTime()) / 60_000);
  if (remainingMinutes <= 0) return "已过期";
  if (remainingMinutes < 60) return `${remainingMinutes} 分钟后过期`;

  const remainingHours = Math.ceil(remainingMinutes / 60);
  if (remainingHours < 24) return `约 ${remainingHours} 小时后过期`;

  return `约 ${Math.ceil(remainingHours / 24)} 天后过期`;
}

export function formFromEnvironment(environment: ExplorationEnvironment): EnvironmentForm {
  return {
    projectId: environment.project_id,
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

export function isManualAuthEnabled(environment: ExplorationEnvironment | null) {
  return Boolean(
    environment &&
      environment.login_strategy === "account_password" &&
      environment.captcha_strategy === "manual" &&
      environment.reuse_auth_state,
  );
}

export function isAiLetterAutoAuthEnabled(environment: ExplorationEnvironment | null) {
  return Boolean(
    environment &&
      environment.login_strategy === "account_password" &&
      environment.captcha_strategy === "ai_letter" &&
      environment.reuse_auth_state,
  );
}

export function canStartAiLetterAutoAuth(environment: ExplorationEnvironment) {
  return isAiLetterAutoAuthEnabled(environment) && environment.has_saved_credentials;
}

export function formMatchesSavedManualAuthConfig(environment: ExplorationEnvironment | null, form: EnvironmentForm) {
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

export function isActiveManualAuthSession(session: ManualAuthSession | null) {
  return Boolean(session && ACTIVE_MANUAL_AUTH_SESSION_STATUSES.has(session.status));
}

export function ExplorationStatusBadge({ status }: { status: string }) {
  const isLoading = LOADING_EXPLORATION_STATUSES.has(status);

  return (
    <StatusBadge tone={explorationStatusTone(status)}>
      {isLoading ? <Loader className="-ml-0.5" size={12} /> : null}
      {explorationStatusLabels[status] ?? status}
    </StatusBadge>
  );
}

export function EnvironmentAuthStateBadge({ message, status }: { message?: string; status: string }) {
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

export function isManualAuthSessionEnded(session: ManualAuthSession) {
  return ["ended", "cancelled", "saved", "auto_saved"].includes(session.status);
}

export function isMissingManualAuthSessionError(error: unknown) {
  return error instanceof ApiRequestError && error.code === "MANUAL_AUTH_SESSION_NOT_FOUND";
}
