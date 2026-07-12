"use client";

import { toast } from "sonner";

import { ApiRequestError, apiRequest } from "@/lib/api-client";

type ErrorFeedbackOptions = {
  title?: string;
  fallbackMessage: string;
  actionLabel?: string;
  method?: string;
  path?: string;
};

type ReportedError = {
  title: string;
  message: string;
  status?: number;
  code?: string;
  traceId?: string;
  method?: string;
  path?: string;
  pageUrl: string;
  actionLabel?: string;
  occurredAt: string;
};

const SENSITIVE_QUERY_PATTERN = /(token|key|secret|password|authorization|cookie|captcha|verification)/i;

export function reportError(error: unknown, options: ErrorFeedbackOptions): ReportedError {
  const apiError = error instanceof ApiRequestError ? error : null;
  const title = options.title ?? options.fallbackMessage;
  const message = safeErrorMessage(error, options.fallbackMessage);
  const item: ReportedError = {
    title,
    message,
    status: apiError?.status,
    code: apiError?.code || undefined,
    traceId: apiError?.traceId || undefined,
    method: options.method,
    path: options.path ? sanitizePath(options.path) : undefined,
    pageUrl: typeof window === "undefined" ? "" : window.location.href,
    actionLabel: options.actionLabel,
    occurredAt: new Date().toISOString(),
  };
  void submitClientErrorLog(item);

  toast.error(title, {
    description: item.traceId ? `追踪 ID：${item.traceId}` : `${message}。错误会写入系统日志。`,
    classNames: {
      title: "select-text",
      description: "select-text",
    },
  });

  return item;
}

async function submitClientErrorLog(error: ReportedError): Promise<void> {
  try {
    await apiRequest("/operation-logs/client-errors", {
      method: "POST",
      body: JSON.stringify({
        title: error.title,
        message: error.message,
        code: error.code ?? "",
        status: error.status ?? null,
        trace_id: error.traceId ?? "",
        method: error.method ?? "",
        path: error.path ?? "",
        page_url: error.pageUrl,
        action_label: error.actionLabel ?? "",
        occurred_at: error.occurredAt,
      }),
    });
  } catch {
    return;
  }
}

function safeErrorMessage(error: unknown, fallbackMessage: string) {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : fallbackMessage;
  return maskSensitiveText(message || fallbackMessage).slice(0, 500);
}

function sanitizePath(path: string) {
  const [pathname, query] = path.split("?");
  if (!query) return pathname;
  const params = new URLSearchParams(query);
  for (const key of Array.from(params.keys())) {
    if (SENSITIVE_QUERY_PATTERN.test(key)) {
      params.set(key, "******");
    }
  }
  const safeQuery = params.toString();
  return safeQuery ? `${pathname}?${safeQuery}` : pathname;
}

function maskSensitiveText(value: string) {
  return value.replace(
    /(password|token|api[_-]?key|secret|authorization|cookie|captcha|verification[_-]?code|access[_-]?key)(\s*[:=]\s*)([^\s,;]+)/gi,
    "$1$2******",
  );
}
