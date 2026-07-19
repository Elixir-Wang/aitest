"use client";

import { useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import { CheckCircle2, FileCode2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiRequestError,
  confirmPerformanceScript,
  createPerformanceRun,
  getPerformanceScript,
  type PerformanceScript,
  updatePerformanceScriptConfiguration,
} from "@/lib/api-client";

export function ScriptReview({ projectId, testId, scriptId }: { projectId: string; testId: string; scriptId: string }) {
  const router = useRouter();
  const [script, setScript] = useState<PerformanceScript | null>(null);
  const [headers, setHeaders] = useState("{}");
  const [body, setBody] = useState("null");
  const [successRules, setSuccessRules] = useState("[]");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getPerformanceScript(projectId, testId, scriptId)
      .then((result) => {
        setScript(result);
        const preview = result.runtime_preview;
        const planRequest = (result.plan.request ?? {}) as { headers?: unknown; body?: unknown };
        const requestHeaders = preview?.request?.headers ?? planRequest.headers ?? {};
        const requestBody = preview?.request?.body ?? planRequest.body ?? null;
        const rules = preview?.success_rules ?? result.plan.success_rules ?? [];
        setHeaders(JSON.stringify(requestHeaders, null, 2));
        setBody(JSON.stringify(requestBody, null, 2));
        setSuccessRules(JSON.stringify(rules, null, 2));
      })
      .catch((error) => toast.error(apiErrorMessage(error)));
  }, [projectId, scriptId, testId]);

  if (!script) return <div className="border-y py-16 text-center text-muted-foreground text-sm">正在加载脚本</div>;
  const editable =
    script.validation_status === "pending_confirmation" || script.validation_status === "validation_failed";

  async function saveConfiguration() {
    setSaving(true);
    try {
      const updated = await updatePerformanceScriptConfiguration(projectId, testId, scriptId, {
        request: { headers: JSON.parse(headers), body: JSON.parse(body) },
        success_rules: JSON.parse(successRules),
      });
      setScript(updated);
      const preview = updated.runtime_preview;
      const planRequest = (updated.plan.request ?? {}) as { headers?: unknown; body?: unknown };
      setHeaders(JSON.stringify(preview?.request?.headers ?? planRequest.headers ?? {}, null, 2));
      setBody(JSON.stringify(preview?.request?.body ?? planRequest.body ?? null, null, 2));
      setSuccessRules(JSON.stringify(preview?.success_rules ?? updated.plan.success_rules ?? [], null, 2));
      toast.success("脚本配置已重新渲染并校验");
    } catch (error) {
      toast.error(error instanceof SyntaxError ? "配置必须是有效 JSON" : apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    setSaving(true);
    try {
      const updated = await confirmPerformanceScript(projectId, testId, scriptId);
      setScript(updated);
      toast.success("脚本已确认，可用于正式压测");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function startRun() {
    setSaving(true);
    try {
      const run = await createPerformanceRun(projectId, testId, scriptId);
      router.push(`/projects/${projectId}/performance-tests/${testId}/runs/${run.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <section className="flex flex-col gap-3 border-y py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg border bg-muted/40">
            <FileCode2 className="size-5" />
          </div>
          <div>
            <p className="font-semibold">脚本版本 v{script.version}</p>
            <p className="text-muted-foreground text-xs">
              模板 {script.template_version} · {script.generation_source}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={script.validation_result.valid ? "secondary" : "destructive"}>
            {statusLabel(script.validation_status)}
          </Badge>
          {editable ? (
            <Button disabled={saving || !script.validation_result.valid} onClick={confirm}>
              <ShieldCheck className="mr-2 size-4" />
              确认脚本
            </Button>
          ) : null}
          {script.validation_status === "confirmed" ? (
            <Button disabled={saving} onClick={startRun}>
              进入 Locust 控制台
            </Button>
          ) : null}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <section className="space-y-4">
          <div>
            <h2 className="font-semibold text-sm">结构化请求配置</h2>
            <p className="mt-1 text-muted-foreground text-xs">只允许调整请求数据和成功规则，生成代码保持只读。</p>
          </div>
          <JsonField disabled={!editable} label="Headers" onChange={setHeaders} value={headers} />
          <JsonField disabled={!editable} label="Body" onChange={setBody} value={body} />
          <JsonField disabled={!editable} label="成功规则" onChange={setSuccessRules} rows={8} value={successRules} />
          {editable ? (
            <Button disabled={saving} onClick={saveConfiguration} variant="outline">
              重新渲染并校验
            </Button>
          ) : null}
          {(script.validation_result.errors ?? []).map((error) => (
            <p className="text-destructive text-xs" key={error}>
              {error}
            </p>
          ))}
          {script.validation_result.valid ? (
            <p className="flex items-center gap-2 text-emerald-700 text-xs dark:text-emerald-300">
              <CheckCircle2 className="size-4" />
              结构、语法和安全校验通过
            </p>
          ) : null}
        </section>

        <section className="min-w-0">
          <h2 className="mb-2 font-semibold text-sm">只读 Locust 脚本</h2>
          <pre className="max-h-[720px] overflow-auto rounded-lg border bg-slate-950 p-4 text-slate-100 text-xs leading-5">
            <code>{script.code}</code>
          </pre>
        </section>
      </div>
    </div>
  );
}

function JsonField({
  label,
  value,
  onChange,
  disabled,
  rows = 6,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  rows?: number;
}) {
  return (
    <div className="block space-y-2 text-sm">
      <p className="font-medium text-xs">{label}</p>
      <Textarea
        className="font-mono text-xs"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        value={value}
      />
    </div>
  );
}

function statusLabel(status: PerformanceScript["validation_status"]) {
  return {
    generating: "生成中",
    validation_failed: "校验失败",
    pending_confirmation: "待确认",
    confirmed: "已确认",
    superseded: "已替代",
  }[status];
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  return "脚本操作失败";
}
