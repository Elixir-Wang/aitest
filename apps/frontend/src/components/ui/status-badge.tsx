import * as React from "react";

import type { VariantProps } from "class-variance-authority";

import { Badge, badgeVariants } from "@/components/ui/badge-2";

export type StatusBadgeTone = "success" | "destructive" | "warning" | "info" | "processing" | "neutral";

export function getStatusBadgeProps(tone: StatusBadgeTone): Pick<
  VariantProps<typeof badgeVariants>,
  "variant" | "appearance"
> {
  switch (tone) {
    case "success":
      return { variant: "success", appearance: "outline" };
    case "destructive":
      return { variant: "destructive", appearance: "outline" };
    case "warning":
      return { variant: "warning", appearance: "outline" };
    case "info":
      return { variant: "info", appearance: "outline" };
    case "processing":
      return { variant: "secondary", appearance: "light" };
    case "neutral":
    default:
      return { variant: "outline" };
  }
}

type StatusBadgeProps = Omit<React.ComponentProps<typeof Badge>, "variant" | "appearance"> & {
  tone: StatusBadgeTone;
};

export function StatusBadge({ tone, className, ...props }: StatusBadgeProps) {
  return <Badge {...getStatusBadgeProps(tone)} className={className} {...props} />;
}

export function healthStatusTone(healthStatus: string): StatusBadgeTone {
  if (healthStatus === "healthy") return "success";
  if (healthStatus === "unhealthy" || healthStatus === "timeout") return "destructive";
  if (healthStatus === "testing") return "processing";
  return "neutral";
}

export function taskStatusGroupTone(statusGroup: string): StatusBadgeTone {
  if (statusGroup === "failed") return "destructive";
  if (statusGroup === "completed") return "success";
  if (statusGroup === "running") return "processing";
  return "neutral";
}

export function taskStatusTone(statusGroup: string, status: string): StatusBadgeTone {
  if (["blocked", "failed", "interrupted"].includes(status)) return "destructive";
  return taskStatusGroupTone(statusGroup);
}

export function operationLogResultTone(result: string): StatusBadgeTone {
  if (result === "failed") return "destructive";
  if (result === "success") return "success";
  if (result === "partial_success") return "warning";
  return "neutral";
}

export function userStatusTone(status: string): StatusBadgeTone {
  return status === "disabled" ? "neutral" : "success";
}

export function projectStatusTone(status: string): StatusBadgeTone {
  return status === "archived" ? "neutral" : "success";
}

export function fileConversionTone(status: string): StatusBadgeTone {
  if (status === "success") return "success";
  if (status === "failed") return "destructive";
  if (status === "warning") return "warning";
  if (status === "pending" || status === "processing") return "processing";
  return "neutral";
}

export function requirementAnalysisStatusTone(status: string): StatusBadgeTone {
  if (status === "failed" || status === "blocked") return "destructive";
  if (status === "completed" || status === "versioned") return "success";
  if (["queued", "running", "parsing"].includes(status)) return "processing";
  if (status === "needs_clarification" || status === "pending_review" || status === "pending_merge") {
    return "warning";
  }
  return "neutral";
}

export function explorationStatusTone(status: string): StatusBadgeTone {
  if (status === "completed") return "success";
  if (status === "blocked" || status === "interrupted") return "destructive";
  if (status === "partial") return "warning";
  if (["pending", "queued", "running", "stopping"].includes(status)) return "processing";
  return "neutral";
}

export function explorationPlanStatusTone(status: string): StatusBadgeTone {
  if (status === "confirmed" || status === "completed") return "success";
  if (status === "blocked") return "destructive";
  if (status === "running") return "processing";
  if (status === "draft") return "warning";
  return "neutral";
}

export function authStateStatusTone(status: string): StatusBadgeTone {
  if (status === "valid") return "success";
  if (status === "expired" || status === "login_failed") return "destructive";
  if (status === "logging_in") return "processing";
  if (status === "unknown") return "warning";
  return "neutral";
}

export function logLevelTone(level: string): StatusBadgeTone {
  if (level === "error") return "destructive";
  if (level === "warning" || level === "warn") return "warning";
  return "neutral";
}

export function severityTone(severity: string): StatusBadgeTone {
  if (severity === "blocker") return "destructive";
  if (severity === "major") return "warning";
  return "neutral";
}

export function goalValidationStatusTone(status: string): StatusBadgeTone {
  if (status === "passed") return "success";
  if (status === "failed") return "destructive";
  if (status === "partial") return "warning";
  if (status === "pending") return "processing";
  return "neutral";
}

export function chineseCompletionTone(status: string): StatusBadgeTone {
  if (["完成", "已采纳", "通过"].includes(status)) return "success";
  if (status === "处理中") return "processing";
  if (["失败", "未通过"].includes(status)) return "destructive";
  return "neutral";
}

export function englishStatusTone(status: string): StatusBadgeTone {
  const normalized = status.trim().toLowerCase();
  if (["done", "completed", "paid", "fulfilled", "active", "passed", "success", "confirmed"].includes(normalized)) {
    return "success";
  }
  if (
    ["failed", "refunded", "returned", "unfulfilled", "cancelled", "canceled", "inactive", "error"].includes(
      normalized,
    )
  ) {
    return "destructive";
  }
  if (["pending", "in progress", "processing", "draft", "upcoming"].includes(normalized)) {
    return "processing";
  }
  if (["partial", "warning"].includes(normalized)) {
    return "warning";
  }
  return "neutral";
}

export function paymentStatusTone(status: string): StatusBadgeTone {
  if (status === "Paid") return "success";
  if (status === "Refunded") return "destructive";
  return "warning";
}

export function fulfillmentStatusTone(status: string): StatusBadgeTone {
  if (status === "Fulfilled") return "success";
  if (status === "Returned") return "destructive";
  return "destructive";
}

export function classScheduleStatusTone(status: string): StatusBadgeTone {
  if (status === "In Progress") return "success";
  if (status === "Completed") return "success";
  if (status === "Cancelled") return "destructive";
  if (status === "Upcoming") return "warning";
  return "neutral";
}
