"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { AlertTriangle, ArrowLeft, Check, Gauge, LoaderCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type ApiAutomationEndpoint,
  type ApiAutomationEnvironment,
  type ApiAutomationTestCase,
  ApiRequestError,
  createPerformanceTest,
  listApiAutomationEndpoints,
  listApiAutomationEnvironments,
  listApiAutomationTestCases,
  type PerformanceRequestPreview,
  previewPerformanceRequest,
} from "@/lib/api-client";

import { LoadProfileRail } from "./load-profile-rail";

type NumericDraft = {
  users: string;
  spawnRate: string;
  measurementSeconds: string;
  waitMin: string;
  waitMax: string;
  timeout: string;
  maxFailPercent: string;
  maxAverageMs: string;
  maxP95Ms: string;
  minRps: string;
};

const initialNumbers: NumericDraft = {
  users: "10",
  spawnRate: "1",
  measurementSeconds: "60",
  waitMin: "1",
  waitMax: "3",
  timeout: "30",
  maxFailPercent: "",
  maxAverageMs: "",
  maxP95Ms: "",
  minRps: "",
};

export function PerformanceTestForm({ projectId }: { projectId: string }) {
  const router = useRouter();
  const previewSequence = useRef(0);
  const [endpoints, setEndpoints] = useState<ApiAutomationEndpoint[]>([]);
  const [environments, setEnvironments] = useState<ApiAutomationEnvironment[]>([]);
  const [testCases, setTestCases] = useState<ApiAutomationTestCase[]>([]);
  const [endpointId, setEndpointId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [sourceCaseId, setSourceCaseId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pathJson, setPathJson] = useState("{}");
  const [queryJson, setQueryJson] = useState("{}");
  const [headersJson, setHeadersJson] = useState("{}");
  const [bodyJson, setBodyJson] = useState("null");
  const [successCodes, setSuccessCodes] = useState("200");
  const [numbers, setNumbers] = useState<NumericDraft>(initialNumbers);
  const [preview, setPreview] = useState<PerformanceRequestPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [requestTouched, setRequestTouched] = useState(false);

  useEffect(() => {
    let ignore = false;
    Promise.all([
      listApiAutomationEndpoints(projectId),
      listApiAutomationEnvironments(projectId),
      listApiAutomationTestCases(projectId),
    ])
      .then(([endpointRows, environmentRows, caseRows]) => {
        if (ignore) return;
        setEndpoints(endpointRows);
        setEnvironments(environmentRows);
        setTestCases(caseRows);
        const firstEndpoint = endpointRows[0]?.id ?? "";
        setEndpointId(firstEndpoint);
        setEnvironmentId(environmentRows[0]?.id ?? "");
        if (environmentRows[0]) {
          setNumbers((current) => ({ ...current, timeout: String(environmentRows[0].timeout_seconds) }));
        }
      })
      .catch((error) => toast.error(apiErrorMessage(error, "接口资产加载失败")));
    return () => {
      ignore = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (!endpointId) return;
    const sequence = ++previewSequence.current;
    setPreviewing(true);
    previewPerformanceRequest(projectId, {
      endpoint_id: endpointId,
      source_api_test_case_id: sourceCaseId || null,
    })
      .then((result) => {
        if (sequence !== previewSequence.current) return;
        setPreview(result);
        setPathJson(formatJson(result.request_config.path_parameters));
        setQueryJson(formatJson(result.request_config.query_parameters));
        setHeadersJson(formatJson(result.request_config.headers));
        setBodyJson(formatJson(result.request_config.body));
        const statusRule = result.success_rules.find((rule) => rule.kind === "status_code");
        setSuccessCodes((statusRule?.status_codes ?? [200]).join(", "));
        setRequestTouched(false);
        setName((current) => current.trim() || `${result.endpoint.name}性能测试`);
      })
      .catch((error) => {
        if (sequence === previewSequence.current) toast.error(apiErrorMessage(error, "请求配置预览失败"));
      })
      .finally(() => {
        if (sequence === previewSequence.current) setPreviewing(false);
      });
  }, [endpointId, projectId, sourceCaseId]);

  const endpointCases = useMemo(
    () => testCases.filter((item) => item.endpoint_id === endpointId),
    [endpointId, testCases],
  );

  const selectedEndpoint = endpoints.find((item) => item.id === endpointId) ?? null;
  const users = numberValue(numbers.users, 1);
  const spawnRate = numberValue(numbers.spawnRate, 1);
  const measurementSeconds = numberValue(numbers.measurementSeconds, 1);

  function changeEndpoint(nextEndpointId: string) {
    setEndpointId(nextEndpointId);
    setSourceCaseId("");
    setPreview(null);
  }

  function changeSourceCase(nextSourceCaseId: string) {
    if (requestTouched && !window.confirm("切换来源用例会重置当前请求配置，继续？")) return;
    setSourceCaseId(nextSourceCaseId);
  }

  function changeEnvironment(nextEnvironmentId: string) {
    setEnvironmentId(nextEnvironmentId);
    const environment = environments.find((item) => item.id === nextEnvironmentId);
    if (environment) setNumbers((current) => ({ ...current, timeout: String(environment.timeout_seconds) }));
  }

  function updateNumber(field: keyof NumericDraft, value: string) {
    setNumbers((current) => ({ ...current, [field]: value }));
  }

  async function submit() {
    if (!name.trim() || !endpointId || !environmentId) {
      toast.error("请填写名称并选择接口和环境");
      return;
    }
    try {
      const pathParameters = parseObject(pathJson, "Path 参数");
      const queryParameters = parseObject(queryJson, "Query 参数");
      const headers = parseObject(headersJson, "Headers");
      const body = parseJson(bodyJson, "Request Body");
      const waitMin = positiveNumber(numbers.waitMin, "最小等待时间", 0.1);
      const waitMax = positiveNumber(numbers.waitMax, "最大等待时间", 0.1);
      if (waitMax < waitMin) throw new Error("最大等待时间不能小于最小等待时间");
      const codes = successCodes
        .split(",")
        .map((value) => Number(value.trim()))
        .filter(Number.isInteger);
      if (codes.length === 0 || codes.some((code) => code < 100 || code > 599)) {
        throw new Error("成功状态码格式不正确");
      }

      setSaving(true);
      const created = await createPerformanceTest(projectId, {
        name: name.trim(),
        description: description.trim(),
        target_type: "endpoint",
        endpoint_id: endpointId,
        api_environment_id: environmentId,
        source_api_test_case_id: sourceCaseId || null,
        request_config: {
          path_parameters: pathParameters,
          query_parameters: queryParameters,
          headers,
          body,
          random_seed: null,
        },
        load_config: {
          users: positiveInteger(numbers.users, "并发用户数"),
          spawn_rate: positiveNumber(numbers.spawnRate, "启动速率"),
          measurement_duration_seconds: positiveInteger(numbers.measurementSeconds, "正式测量时长"),
          wait_time_min_seconds: waitMin,
          wait_time_max_seconds: waitMax,
          request_timeout_seconds: positiveNumber(numbers.timeout, "请求超时"),
        },
        performance_goal: compactGoal(numbers),
        success_rules: [{ kind: "status_code", status_codes: codes }],
      });
      toast.success("性能测试已创建");
      router.push(`/projects/${projectId}/performance-tests/${created.id}`);
    } catch (error) {
      toast.error(apiErrorMessage(error, "性能测试创建失败"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <ol className="border-l text-sm">
          {["目标接口", "请求数据", "负载模型", "性能目标"].map((label, index) => (
            <li className="flex items-center gap-2 border-b py-3 pl-3" key={label}>
              <span className="flex size-5 items-center justify-center rounded-full bg-muted font-medium text-[11px]">
                {index + 1}
              </span>
              {label}
            </li>
          ))}
        </ol>
        <Button className="mt-4 w-full" onClick={() => void submit()} disabled={saving || previewing}>
          {saving ? <LoaderCircle className="animate-spin" /> : <Check />}
          创建性能测试
        </Button>
        <Button className="mt-2 w-full" onClick={() => router.back()} variant="ghost">
          <ArrowLeft />
          返回
        </Button>
      </aside>

      <div className="min-w-0 divide-y border-y">
        <FormSection description="任务定义和接口自动化资产引用。" title="目标接口">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="任务名称">
              <Input maxLength={120} onChange={(event) => setName(event.target.value)} value={name} />
            </Field>
            <Field label="接口">
              <NativeSelect onChange={(event) => changeEndpoint(event.target.value)} value={endpointId}>
                <option value="">选择接口</option>
                {endpoints.map((endpoint) => (
                  <option key={endpoint.id} value={endpoint.id}>
                    {endpoint.method} {endpoint.path} {endpoint.summary ? `· ${endpoint.summary}` : ""}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="接口环境">
              <NativeSelect onChange={(event) => changeEnvironment(event.target.value)} value={environmentId}>
                <option value="">选择环境</option>
                {environments.map((environment) => (
                  <option key={environment.id} value={environment.id}>
                    {environment.name}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="请求数据来源">
              <NativeSelect onChange={(event) => changeSourceCase(event.target.value)} value={sourceCaseId}>
                <option value="">OpenAPI 示例或默认值</option>
                {endpointCases.map((testCase) => (
                  <option key={testCase.id} value={testCase.id}>
                    {testCase.title}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field className="md:col-span-2" label="说明">
              <Textarea onChange={(event) => setDescription(event.target.value)} rows={3} value={description} />
            </Field>
          </div>
          {selectedEndpoint ? (
            <div className="mt-4 flex items-center gap-2 border-sky-500 border-l-2 bg-sky-50 px-3 py-2 text-xs dark:bg-sky-950/30">
              <Gauge className="size-4" />
              <strong>{selectedEndpoint.method}</strong>
              <code className="truncate">{selectedEndpoint.path}</code>
            </div>
          ) : null}
        </FormSection>

        <FormSection description="敏感 Header 由所选接口环境注入。" title="请求数据">
          {previewing ? <p className="mb-3 text-muted-foreground text-xs">正在生成请求预览</p> : null}
          {preview?.warnings.map((warning) => (
            <div
              className="mb-2 flex items-start gap-2 bg-amber-50 px-3 py-2 text-amber-800 text-xs dark:bg-amber-950/30 dark:text-amber-200"
              key={warning}
            >
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              {warning}
            </div>
          ))}
          <div className="grid gap-4 xl:grid-cols-2">
            <JsonField label="Path 参数" onChange={setPathJson} setTouched={setRequestTouched} value={pathJson} />
            <JsonField label="Query 参数" onChange={setQueryJson} setTouched={setRequestTouched} value={queryJson} />
            <JsonField label="Headers" onChange={setHeadersJson} setTouched={setRequestTouched} value={headersJson} />
            <JsonField label="Request Body" onChange={setBodyJson} setTouched={setRequestTouched} value={bodyJson} />
          </div>
          <Field className="mt-4 max-w-sm" label="成功状态码">
            <Input onChange={(event) => setSuccessCodes(event.target.value)} value={successCodes} />
          </Field>
        </FormSection>

        <FormSection description="闭合并发用户模型，达到目标用户数后开始计时。" title="负载模型">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <NumberField label="并发用户数" onChange={(value) => updateNumber("users", value)} value={numbers.users} />
            <NumberField
              label="每秒启动用户"
              onChange={(value) => updateNumber("spawnRate", value)}
              value={numbers.spawnRate}
            />
            <NumberField
              label="正式测量时长（秒）"
              onChange={(value) => updateNumber("measurementSeconds", value)}
              value={numbers.measurementSeconds}
            />
            <NumberField
              label="最小等待时间（秒）"
              min="0.1"
              onChange={(value) => updateNumber("waitMin", value)}
              step="0.1"
              value={numbers.waitMin}
            />
            <NumberField
              label="最大等待时间（秒）"
              min="0.1"
              onChange={(value) => updateNumber("waitMax", value)}
              step="0.1"
              value={numbers.waitMax}
            />
            <NumberField
              label="请求超时（秒）"
              onChange={(value) => updateNumber("timeout", value)}
              value={numbers.timeout}
            />
          </div>
          <LoadProfileRail measurementSeconds={measurementSeconds} spawnRate={spawnRate} users={users} />
        </FormSection>

        <FormSection description="留空表示只展示 Locust 原始结果。" title="性能目标">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <NumberField
              label="最大失败率（%）"
              min="0"
              onChange={(value) => updateNumber("maxFailPercent", value)}
              step="0.1"
              value={numbers.maxFailPercent}
            />
            <NumberField
              label="最大平均响应（ms）"
              onChange={(value) => updateNumber("maxAverageMs", value)}
              value={numbers.maxAverageMs}
            />
            <NumberField
              label="最大 P95（ms）"
              onChange={(value) => updateNumber("maxP95Ms", value)}
              value={numbers.maxP95Ms}
            />
            <NumberField
              label="最低平均 RPS"
              onChange={(value) => updateNumber("minRps", value)}
              step="0.1"
              value={numbers.minRps}
            />
          </div>
        </FormSection>
      </div>
    </div>
  );
}

function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="px-1 py-6 sm:px-4">
      <div className="mb-4">
        <h2 className="font-semibold text-sm">{title}</h2>
        <p className="text-muted-foreground text-xs">{description}</p>
      </div>
      {children}
    </section>
  );
}

function Field({ label, className = "", children }: { label: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={className}>
      <Label className="mb-2">{label}</Label>
      {children}
    </div>
  );
}

function JsonField({
  label,
  value,
  onChange,
  setTouched,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  setTouched: (value: boolean) => void;
}) {
  return (
    <Field label={label}>
      <Textarea
        className="min-h-28 resize-y font-mono text-xs"
        onChange={(event) => {
          onChange(event.target.value);
          setTouched(true);
        }}
        spellCheck={false}
        value={value}
      />
    </Field>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min = "0",
  step = "1",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  step?: string;
}) {
  return (
    <Field label={label}>
      <Input min={min} onChange={(event) => onChange(event.target.value)} step={step} type="number" value={value} />
    </Field>
  );
}

function NativeSelect(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      {...props}
    />
  );
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function parseJson(value: string, label: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    throw new Error(`${label} 必须是有效 JSON`);
  }
}

function parseObject(value: string, label: string): Record<string, unknown> {
  const parsed = parseJson(value, label);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} 必须是 JSON 对象`);
  return parsed as Record<string, unknown>;
}

function positiveInteger(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${label} 必须是正整数`);
  return parsed;
}

function positiveNumber(value: string, label: string, min = Number.EPSILON) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min) throw new Error(`${label} 必须大于等于 ${min}`);
  return parsed;
}

function numberValue(value: string, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function compactGoal(numbers: NumericDraft) {
  const goal: Record<string, number> = {};
  if (numbers.maxFailPercent) goal.max_fail_ratio = positiveNumber(numbers.maxFailPercent, "最大失败率", 0) / 100;
  if (numbers.maxAverageMs)
    goal.max_average_response_time_ms = positiveNumber(numbers.maxAverageMs, "最大平均响应时间");
  if (numbers.maxP95Ms) goal.max_p95_response_time_ms = positiveNumber(numbers.maxP95Ms, "最大 P95");
  if (numbers.minRps) goal.min_average_rps = positiveNumber(numbers.minRps, "最低平均 RPS");
  return goal;
}

function apiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiRequestError) return error.traceId ? `${error.message}（${error.traceId}）` : error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}
