"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { AlertTriangle, Gauge } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ApiRequestError,
  createLocustUiSession,
  createPerformanceRun,
  getPerformanceTest,
  listPerformanceScripts,
  type PerformanceScript,
  type PerformanceTest,
} from "@/lib/api-client";

import { LoadProfileRail } from "./load-profile-rail";

export function PerformanceTestDetail({ projectId, testId }: { projectId: string; testId: string }) {
  const router = useRouter();
  const [item, setItem] = useState<PerformanceTest | null>(null);
  const [scripts, setScripts] = useState<PerformanceScript[]>([]);
  const [loading, setLoading] = useState(false);
  const autoStarted = useRef(false);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    Promise.all([getPerformanceTest(projectId, testId), listPerformanceScripts(projectId, testId)])
      .then(([result, scriptItems]) => {
        if (ignore) return;
        setItem(result);
        setScripts(scriptItems);

        // Auto-launch if there's a confirmed script
        const confirmedScript = scriptItems.find((s) => s.validation_status === "confirmed");
        if (confirmedScript && !autoStarted.current) {
          autoStarted.current = true;
          launchLocust(confirmedScript);
        }
      })
      .catch((error) => toast.error(apiErrorMessage(error)))
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [projectId, testId]);

  if (!item) {
    return <div className="border-y py-16 text-center text-muted-foreground text-sm">正在加载性能测试</div>;
  }

  const referenceInvalid = !item.endpoint_id || !item.api_environment_id;

  async function launchLocust(script: PerformanceScript) {
    setLoading(true);
    try {
      const run = await createPerformanceRun(projectId, testId, script.id);
      const session = await createLocustUiSession(projectId, run.id);
      window.open(session.url, "_blank");
    } catch (error) {
      toast.error(apiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="divide-y border-y">
      <section className="grid gap-4 py-5 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="接口" value={item.endpoint_id ? `${item.endpoint_method} ${item.endpoint_path}` : "引用已失效"} />
        <Fact label="环境" value={item.api_environment_id ? item.environment_name : "引用已失效"} />
        <Fact label="最近运行" value={item.latest_run_status || "未运行"} />
        <Fact
          label="目标结果"
          value={item.latest_goal_status || (Object.keys(item.performance_goal).length ? "待评估" : "未配置")}
        />
      </section>

      {referenceInvalid ? (
        <div className="flex items-center gap-2 bg-amber-50 px-4 py-3 text-amber-800 text-sm dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle className="size-4" />
          接口或环境引用已失效，不能生成脚本或启动运行。
        </div>
      ) : null}

      <section className="flex items-center justify-between gap-4 py-4">
        <div>
          <p className="font-medium text-sm">Locust 脚本</p>
          <p className="text-muted-foreground text-xs">脚本已通过验证，可直接启动 Locust。</p>
        </div>
        <Button
          disabled={referenceInvalid || loading}
          onClick={() => {
            const confirmedScript = scripts.find((s) => s.validation_status === "confirmed");
            if (confirmedScript) {
              launchLocust(confirmedScript);
            } else {
              toast.error("没有已确认的脚本，请先生成并确认脚本");
            }
          }}
        >
          {loading ? "启动中" : "启动 Locust"}
        </Button>
      </section>

      <section className="grid gap-6 py-6 lg:grid-cols-2">
        <div>
          <SectionTitle icon={Gauge} title="负载配置" />
          <LoadProfileRail
            measurementSeconds={item.load_config.measurement_duration_seconds}
            spawnRate={item.load_config.spawn_rate}
            users={item.load_config.users}
          />
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Definition
              label="等待时间"
              value={`${item.load_config.wait_time_min_seconds} - ${item.load_config.wait_time_max_seconds} 秒`}
            />
            <Definition label="请求超时" value={`${item.load_config.request_timeout_seconds} 秒`} />
          </dl>
        </div>
        <div>
          <SectionTitle title="成功规则与目标" />
          <div className="space-y-3 text-sm">
            <div>
              <p className="mb-1 text-muted-foreground text-xs">成功状态码</p>
              <div className="flex flex-wrap gap-1">
                {(item.success_rules.find((rule) => rule.kind === "status_code")?.status_codes ?? []).map((code) => (
                  <Badge key={code} variant="outline">
                    {code}
                  </Badge>
                ))}
              </div>
            </div>
            <pre className="max-h-48 overflow-auto rounded-lg border bg-muted/30 p-3 text-xs">
              {JSON.stringify(item.performance_goal, null, 2)}
            </pre>
          </div>
        </div>
      </section>

      <section className="py-6">
        <SectionTitle title="请求配置" />
        <pre className="max-h-96 overflow-auto rounded-lg border bg-muted/30 p-3 text-xs">
          {JSON.stringify(item.request_config, null, 2)}
        </pre>
      </section>

      <section className="py-6">
        <SectionTitle title="脚本版本" />
        {scripts.length ? (
          <div className="divide-y border-y">
            {scripts.map((script) => (
              <button
                className="block w-full px-1 py-3 text-left text-sm hover:bg-muted/40"
                key={script.id}
                onClick={() => router.push(`/projects/${projectId}/performance-tests/${testId}/scripts/${script.id}`)}
                type="button"
              >
                v{script.version} · {script.validation_status}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">尚未生成脚本</p>
        )}
      </section>
    </div>
  );
}

function SectionTitle({ icon: Icon, title }: { icon?: typeof Gauge; title: string }) {
  return Icon ? (
    <div className="mb-3 flex items-center gap-2 font-semibold text-sm">
      <Icon className="size-4" />
      {title}
    </div>
  ) : (
    <h2 className="mb-3 font-semibold text-sm">{title}</h2>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-1">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 font-medium text-sm">{value}</p>
    </div>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-slate-300 border-l-2 px-2 py-1 dark:border-slate-700">
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="font-medium text-sm">{value}</dd>
    </div>
  );
}

function apiErrorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  }
  return "性能测试操作失败";
}
