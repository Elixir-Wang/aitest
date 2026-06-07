"use client";

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ArrowLeft, RefreshCw } from "lucide-react";

import { OperationLogDetailContent } from "@/components/ai-testing/operation-logs/operation-log-detail-content";
import { PageShell, ShellSection } from "@/components/ai-testing/page-shell";
import { Button } from "@/components/ui/button";
import {
  type ApiOperationLogDetail,
  apiRequest,
  operationLogActionToLabel,
  operationLogModuleToLabel,
} from "@/lib/api-client";

export default function Page() {
  const params = useParams<{ logId: string }>();
  const [detail, setDetail] = useState<ApiOperationLogDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setDetail(await apiRequest<ApiOperationLogDetail>(`/operation-logs/${params.logId}`));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "日志详情加载失败");
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [params.logId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  return (
    <PageShell
      actions={
        <Button asChild variant="outline">
          <Link href="/settings/logs">
            <ArrowLeft className="size-4" />
            返回日志列表
          </Link>
        </Button>
      }
      breadcrumbs={["系统管理", "日志", "日志详情"]}
      description="查看单条系统日志的上下文、追踪 ID 和脱敏后的错误摘要。"
      projectScope="none"
      title="日志详情"
    >
      <ShellSection className="space-y-4">
        {loading ? <div className="text-muted-foreground text-sm">正在加载日志详情</div> : null}
        {error ? (
          <div className="flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <div className="text-destructive">{error}</div>
            <Button className="w-fit" onClick={loadDetail} variant="outline">
              <RefreshCw className="size-4" />
              重试
            </Button>
          </div>
        ) : null}
        {detail ? (
          <>
            <div className="text-muted-foreground text-sm">
              {operationLogModuleToLabel(detail.module)} / {operationLogActionToLabel(detail.action)}
            </div>
            <OperationLogDetailContent detail={detail} />
          </>
        ) : null}
      </ShellSection>
    </PageShell>
  );
}
